# token_cache.py

import json
import os
import time
from typing import Dict, List

CACHE_FILE = "token_cache.json"
MAX_LIFETIME_SECONDS = 3 * 3600  # 3 hours
CHECK_INTERVAL_SECONDS = 300     # 5 minutes
token_cache: Dict[str, dict] = {}

def load_cache():
    global token_cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                token_cache = json.load(f)
        except Exception as e:
            print(f"[ERROR] Failed to load token cache: {e}")
            token_cache = {}
    else:
        token_cache = {}

def save_cache():
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(token_cache, f)
    except Exception as e:
        print(f"[ERROR] Failed to save token cache: {e}")

def add_token_if_new(mint: str, token_data: dict):
    now = int(time.time())
    if mint not in token_cache:
        print(f"[CACHE] Adding new token {mint} to cache.")
        token_cache[mint] = {
            "data": token_data,
            "created": now,
            "last_seen": now,
            "last_checked": 0,
            "expires_at": now + MAX_LIFETIME_SECONDS
        }
        save_cache()
    else:
        token_cache[mint]["last_seen"] = now
        save_cache()

def update_check(mint: str, signal_strength: int = 0):
    """Mark a token as rechecked and optionally extend its tracking time."""
    if mint not in token_cache:
        return
    token_cache[mint]["last_checked"] = int(time.time())
    if signal_strength > 0:
        token_cache[mint]["expires_at"] = int(time.time()) + 3600  # extend 1 hour
        print(f"[CACHE] Token {mint} extended due to positive signal.")
    save_cache()

def get_due_for_check(interval: int = CHECK_INTERVAL_SECONDS) -> List[dict]:
    """Returns tokens that haven't been checked recently."""
    now = int(time.time())
    return [
        entry for entry in token_cache.values()
        if now - entry.get("last_checked", 0) >= interval
    ]

def get_ready_for_purge() -> List[str]:
    """Returns list of tokens that have expired (no activity, no signals)."""
    now = int(time.time())
    to_remove = []
    for mint, entry in token_cache.items():
        if now > entry.get("expires_at", 0):
            to_remove.append(mint)
    return to_remove

def remove_token(mint: str):
    if mint in token_cache:
        print(f"[CACHE] Manually removing token {mint}")
        del token_cache[mint]
        save_cache()

def cleanup_expired_tokens():
    now = int(time.time())
    expired = [mint for mint, entry in token_cache.items() if now - entry["last_seen"] > MAX_LIFETIME_SECONDS]
    for mint in expired:
        print(f"[CACHE] Removing expired token {mint}")
        del token_cache[mint]
    if expired:
        save_cache()

load_cache()
