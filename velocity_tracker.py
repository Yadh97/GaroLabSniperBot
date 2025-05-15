import time
from collections import defaultdict, deque

# Constants
TIME_WINDOW_SECONDS = 180  # Analyze last 3 minutes
MAX_HISTORY_PER_TOKEN = 100
VELOCITY_CACHE_TTL = 600  # Keep tokens in memory for 10 minutes max

# Structure: { mint: deque([{"timestamp": t, "sol": x}, ...]) }
buy_history = defaultdict(deque)
last_seen = {}

def record_buy_event(mint: str, sol_amount: float):
    now = time.time()
    last_seen[mint] = now

    event = {"timestamp": now, "sol": sol_amount}
    buy_history[mint].append(event)

    # Cap length
    if len(buy_history[mint]) > MAX_HISTORY_PER_TOKEN:
        buy_history[mint].popleft()

def score_token_velocity(mint: str) -> float:
    now = time.time()
    window_start = now - TIME_WINDOW_SECONDS

    events = [e for e in buy_history[mint] if e["timestamp"] >= window_start]
    if not events:
        return 0.0

    total_sol = sum(e["sol"] for e in events)
    num_buys = len(events)
    duration = max(1, now - events[0]["timestamp"])

    # Sol per second gives more weight to fast-moving tokens
    sol_per_sec = total_sol / duration

    # Score is a combination of speed and count
    score = (sol_per_sec * 50) + (num_buys * 5)

    return min(score, 100.0)  # Cap at 100

def purge_old_velocity_data():
    now = time.time()
    expired = [mint for mint, ts in last_seen.items() if now - ts > VELOCITY_CACHE_TTL]
    for mint in expired:
        del buy_history[mint]
        del last_seen[mint]
