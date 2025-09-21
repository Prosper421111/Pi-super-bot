import time
import requests
import threading
from stellar_sdk import Keypair, Server, TransactionBuilder, Asset, exceptions

NETWORK_PASSPHRASE = "Pi Network"
API_BASE = "https://api.mainnet.minepi.com"
RESERVE_AMOUNT = 1  # Minimum balance to keep

# -----------------------------
# Helper to write logs to Streamlit
# -----------------------------
def log(msg, log_area=None):
    if log_area:
        log_area.text(msg)
    print(msg)

# -----------------------------
# Stellar SDK transaction
# -----------------------------
def send_pi(sender_public, sender_secret, receiver_address, amount, log_area=None):
    try:
        server = Server(API_BASE)
        keypair = Keypair.from_secret(sender_secret)
        account = server.load_account(sender_public)
        fee = server.fetch_base_fee()
        
        amount_to_send = max(0, float(amount) - RESERVE_AMOUNT)
        if amount_to_send <= 0:
            log(f"Amount too small to send: {amount}", log_area)
            return None
        
        tx = (
            TransactionBuilder(account, fee=str(fee), network_passphrase=NETWORK_PASSPHRASE)
            .add_payment_op(destination=receiver_address, amount=str(amount_to_send), asset=Asset.native())
            .set_timeout(30)
            .build()
        )
        tx.sign(keypair)
        result = server.submit_transaction(tx)
        log(f"Sent {amount_to_send} PI to {receiver_address}, tx hash: {result.hash}", log_area)
        return result.hash
    except exceptions.BaseHorizonError as e:
        log(f"Transaction failed: {e}", log_area)
        return None
    except Exception as e:
        log(f"Unexpected error: {e}", log_area)
        return None

# -----------------------------
# API helpers
# -----------------------------
def api_call(method, endpoint, token=None, payload=None):
    url = f"https://api.pi-network.dev/v1{endpoint}"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        if method.upper() == "GET":
            r = requests.get(url, headers=headers, timeout=10)
        else:
            r = requests.post(url, headers=headers, json=payload, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"API call failed: {e}")
        return None

# -----------------------------
# Bot actions
# -----------------------------
def login(wallet_phrase, log_area=None):
    payload = {"phrase": wallet_phrase}
    data = api_call("POST", "/wallet/login", payload=payload)
    if data and "token" in data:
        log("Login successful", log_area)
        return data["token"]
    log("Login failed", log_area)
    return None

def get_locked(token):
    return api_call("GET", "/wallet/locked", token=token) or []

def move_locked_to_available(token, tx_id, log_area=None):
    data = api_call("POST", f"/wallet/transfer/{tx_id}?type=available", token=token)
    if data:
        log(f"Moved locked tx {tx_id} to available", log_area)
        return True
    return False

def get_available(token):
    data = api_call("GET", "/wallet/available", token=token)
    if isinstance(data, dict) and "amount" in data:
        return float(data["amount"])
    if isinstance(data, (int, float)):
        return float(data)
    return 0

# -----------------------------
# Worker functions for concurrency
# -----------------------------
def send_worker(wallet_phrase, sender_secret, receiver_address, token, log_area, stop_event):
    while not stop_event.is_set():
        available = get_available(token)
        if available > 0:
            send_pi(wallet_phrase, sender_secret, receiver_address, available, log_area)
        time.sleep(1)

def move_worker(token, log_area, stop_event):
    while not stop_event.is_set():
        locked_list = get_locked(token)
        now = int(time.time())
        for tx in locked_list:
            if tx["unlock_date"] <= now:
                move_locked_to_available(token, tx["id"], log_area)
        time.sleep(1)

# -----------------------------
# Main Bot
# -----------------------------
def run_bot(wallet_phrase, sender_secret, receiver_address, trials=10, log_area=None):
    token = login(wallet_phrase, log_area)
    if not token:
        return None

    # Show initial locked balance
    locked_list = get_locked(token)
    total_locked = 0
    for tx in locked_list:
        unlock_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(tx["unlock_date"]))
        log(f"Locked tx {tx['id']}: {tx['amount']} PI, unlock at {unlock_time}", log_area)
        total_locked += tx["amount"]

    # -----------------------------
    # Start concurrent workers
    # -----------------------------
    stop_event = threading.Event()
    threads = [
        threading.Thread(target=move_worker, args=(token, log_area, stop_event)),
        threading.Thread(target=send_worker, args=(wallet_phrase, sender_secret, receiver_address, token, log_area, stop_event))
    ]
    for t in threads:
        t.start()

    # Run workers for specified trials (seconds)
    try:
        time.sleep(trials * 2)  # total runtime
    finally:
        stop_event.set()
        for t in threads:
            t.join()

    return total_locked
