import threading
import time
import requests
import random
import logging
from threading import Lock

# -----------------------------
# CONFIG - Set these carefully
# -----------------------------
wallet_phrase = 'YOUR PHRASE'
wallet_address = 'YOUR ADDRESS'
api_url = 'https://api.pi-network.dev/v1'

# Safety/testing flags
TEST_MODE = True        # True = simulate responses, False = hit real API
MACHINE_GUN = True      # Use extremely small sleeps when True

# Trials: number of main actions each worker will attempt before stopping
TRIALS = 10

# Machine-gun tuning (dangerous if set too high)
if MACHINE_GUN:
    BASE_SLEEP = 0.005     # 5 ms
    JITTER = 0.002         # up to 2 ms jitter
    MAX_REQUESTS_PER_SECOND = 50
else:
    BASE_SLEEP = 0.2
    JITTER = 0.05
    MAX_REQUESTS_PER_SECOND = 5

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)

# -----------------------------
# Rate limiter (token bucket)
# -----------------------------
class RateLimiter:
    def __init__(self, max_per_second):
        self.capacity = float(max_per_second)
        self.tokens = float(self.capacity)
        self.last = time.monotonic()
        self.lock = Lock()

    def wait_for_token(self):
        while True:
            with self.lock:
                now = time.monotonic()
                elapsed = now - self.last
                self.last = now
                self.tokens += elapsed * self.capacity
                if self.tokens > self.capacity:
                    self.tokens = self.capacity
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
            time.sleep(0.0005)

rate_limiter = RateLimiter(MAX_REQUESTS_PER_SECOND)

# Backoff handling
backoff_lock = Lock()
backoff_seconds = 0.0

def increase_backoff():
    global backoff_seconds
    with backoff_lock:
        if backoff_seconds < 0.5:
            backoff_seconds = 0.5
        else:
            backoff_seconds = min(5.0, backoff_seconds * 2.0)

def maybe_backoff_sleep():
    with backoff_lock:
        b = backoff_seconds
    if b > 0:
        logging.warning(f"Backing off for {b:.2f}s due to earlier 429s.")
        time.sleep(b)

# -----------------------------
# API helpers (TEST_MODE support)
# -----------------------------
def _real_request(method, url, headers=None, json=None, timeout=5):
    return requests.request(method, url, headers=headers, json=json, timeout=timeout)

def api_call(method, url, headers=None, json=None):
    rate_limiter.wait_for_token()
    maybe_backoff_sleep()

    if TEST_MODE:
        logging.debug(f"[TEST_MODE] {method} {url} {json}")
        if '/wallet/login' in url:
            return ({'token': 'FAKE_TOKEN'}, 200)
        if '/wallet/pending' in url:
            return ([], 200)
        if '/wallet/locked' in url:
            return ([], 200)
        if '/wallet/available' in url:
            return (0, 200)
        return ({'ok': True}, 200)

    attempts = 0
    while attempts < 5:
        try:
            resp = _real_request(method, url, headers=headers, json=json, timeout=5)
            status = resp.status_code
            if status == 429:
                logging.warning(f"Received 429 from {url}. Attempt {attempts+1}/5.")
                increase_backoff()
                time.sleep(0.5 + random.random() * 0.5)
                attempts += 1
                continue
            if status >= 500:
                logging.warning(f"Server error {status} on {url}. Attempt {attempts+1}/5.")
                time.sleep(0.1 * 2 ** attempts + random.random() * 0.01)
                attempts += 1
                continue
            try:
                data = resp.json()
            except ValueError:
                logging.warning(f"Non-JSON response from {url} (status {status}).")
                return (None, status)
            return (data, status)
        except requests.exceptions.RequestException as e:
            attempts += 1
            logging.warning(f"Request error {e} ({attempts}/5).")
            time.sleep(0.1 * 2 ** attempts + random.random() * 0.01)
    logging.error(f"API call ultimately failed: {method} {url}")
    return (None, None)

# -----------------------------
# Bot actions
# -----------------------------
def login():
    if TEST_MODE:
        return 'FAKE_TOKEN'
    headers = {'Content-Type': 'application/json'}
    payload = {'phrase': wallet_phrase}
    data, status = api_call('POST', api_url + '/wallet/login', headers=headers, json=payload)
    if not data or not isinstance(data, dict):
        logging.error("Login failed or returned invalid data.")
        return None
    token = data.get('token')
    if not token:
        logging.error("Login returned no token.")
        return None
    logging.info("Login successful.")
    return token

def check_pending(token):
    confirmations = 0
    while confirmations < TRIALS:
        headers = {'Authorization': f'Bearer {token}'}
        data, status = api_call('GET', api_url + '/wallet/pending', headers=headers)
        if isinstance(data, list):
            for tx in data:
                try:
                    if tx.get('type') == 'Mining' and tx.get('state') == 'Pending':
                        api_call('POST', api_url + f"/wallet/confirm/{tx['id']}", headers=headers)
                        confirmations += 1
                        logging.info(f"[pending] Confirmed tx {tx.get('id')} ({confirmations}/{TRIALS})")
                        if confirmations >= TRIALS:
                            break
                except Exception as e:
                    logging.warning(f"[pending] Error: {e}")
        time.sleep(BASE_SLEEP + random.random() * JITTER)
    logging.info("check_pending finished.")

def check_locked(token):
    transfers = 0
    while transfers < TRIALS:
        headers = {'Authorization': f'Bearer {token}'}
        data, status = api_call('GET', api_url + '/wallet/locked', headers=headers)
        if isinstance(data, list):
            now = int(time.time())
            for tx in data:
                try:
                    if tx.get('unlock_date', now + 1) <= now:
                        api_call('POST', api_url + f"/wallet/transfer/{tx['id']}?type=available", headers=headers)
                        transfers += 1
                        logging.info(f"[locked] Transferred tx {tx.get('id')} ({transfers}/{TRIALS})")
                        if transfers >= TRIALS:
                            break
                except Exception as e:
                    logging.warning(f"[locked] Error: {e}")
        time.sleep(BASE_SLEEP + random.random() * JITTER)
    logging.info("check_locked finished.")

def check_available(token):
    sends = 0
    while sends < TRIALS:
        headers = {'Authorization': f'Bearer {token}'}
        data, status = api_call('GET', api_url + '/wallet/available', headers=headers)
        amt = None
        if isinstance(data, (int, float)):
            amt = data
        elif isinstance(data, dict) and 'amount' in data:
            amt = data.get('amount')
        if isinstance(amt, (int, float)) and amt > 0:
            api_call('POST', api_url + '/wallet/send', headers=headers, json={'to': wallet_address, 'amount': amt})
            sends += 1
            logging.info(f"[available] Sent {amt} to {wallet_address} ({sends}/{TRIALS})")
        time.sleep(BASE_SLEEP + random.random() * JITTER)
    logging.info("check_available finished.")

# -----------------------------
# MAIN (for running directly)
# -----------------------------
def main():
    token = login()
    if not token:
        logging.error("Login failed — aborting.")
        return
    threads = [
        threading.Thread(target=check_pending, args=(token,)),
        threading.Thread(target=check_locked, args=(token,)),
        threading.Thread(target=check_available, args=(token,)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    logging.info("All workers finished. Exiting.")

# -----------------------------
# ENTRY FOR STREAMLIT APP
# -----------------------------
def run_bot(wallet_phrase_input, wallet_address_input, trials_input=10, machine_gun=True, test_mode=True):
    global wallet_phrase, wallet_address, TRIALS, MACHINE_GUN, TEST_MODE
    wallet_phrase = wallet_phrase_input
    wallet_address = wallet_address_input
    TRIALS = trials_input
    MACHINE_GUN = machine_gun
    TEST_MODE = test_mode

    logging.info(f"Starting bot: TEST_MODE={TEST_MODE} MACHINE_GUN={MACHINE_GUN} TRIALS={TRIALS}")
    main()
