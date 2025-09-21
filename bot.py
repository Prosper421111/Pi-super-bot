import time
import requests
import threading

# -----------------------------
# Helper for logs
# -----------------------------
def log(msg, log_area=None):
    if log_area:
        log_area.text(msg)
    print(msg)

# -----------------------------
# API calls
# -----------------------------
API_BASE = "https://api.pi-network.dev/v1"

def api_call(method, endpoint, token=None, payload=None):
    url = f"{API_BASE}{endpoint}"
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
        log("Login successful!", log_area)
        return data["token"]
    log("Login failed. Check your wallet phrase.", log_area)
    return None

def get_locked(token):
    return api_call("GET", "/wallet/locked", token=token) or []

def move_locked_to_available(token, tx_id, log_area=None):
    data = api_call("POST", f"/wallet/transfer/{tx_id}?type=available", token=token)
    if data:
        log(f"Moved locked tx {tx_id} → available", log_area)
        return True
    return False

def get_available(token):
    data = api_call("GET", "/wallet/available", token=token)
    if isinstance(data, dict) and "amount" in data:
        return float(data["amount"])
    if isinstance(data, (int, float)):
        return float(data)
    return 0

def send_pi(token, amount, to_address, log_area=None):
    payload = {"to": to_address, "amount": amount}
    data = api_call("POST", "/wallet/send", token=token, payload=payload)
    if data:
        log(f"Sent {amount} PI → {to_address}", log_area)
        return True
    return False

# -----------------------------
# Worker functions (concurrent)
# -----------------------------
def move_worker(token, log_area, stop_event):
    while not stop_event.is_set():
        locked_list = get_locked(token)
        now = int(time.time())
        for tx in locked_list:
            if tx["unlock_date"] <= now:
                move_locked_to_available(token, tx["id"], log_area)
        time.sleep(1)

def send_worker(token, log_area, to_address, stop_event):
    while not stop_event.is_set():
        available = get_available(token)
        if available > 0:
            send_pi(token, available, to_address, log_area)
        time.sleep(1)

# -----------------------------
# Main Bot
# -----------------------------
def run_bot(wallet_phrase, to_address, runtime=30, log_area=None):
    token = login(wallet_phrase, log_area)
    if not token:
        return None

    # Show initial locked balance
    locked_list = get_locked(token)
    total_locked = 0
    if locked_list:
        for tx in locked_list:
            unlock_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(tx["unlock_date"]))
            log(f"Locked tx {tx['id']}: {tx['amount']} PI, unlock at {unlock_time}", log_area)
            total_locked += tx["amount"]
    else:
        log("No locked balance.", log_area)

    # Start concurrent workers
    stop_event = threading.Event()
    threads = [
        threading.Thread(target=move_worker, args=(token, log_area, stop_event)),
        threading.Thread(target=send_worker, args=(token, log_area, to_address, stop_event))
    ]
    for t in threads:
        t.start()

    # Run for the given runtime (seconds)
    try:
        time.sleep(runtime)
    finally:
        stop_event.set()
        for t in threads:
            t.join()

    return total_locked
