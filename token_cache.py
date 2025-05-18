# Filename: token_cache.py

import json
import os
import time
from typing import Dict

# Constants
CACHE_FILE = "token_cache.json"
MAX_LIFETIME_SECONDS = 3 * 3600  # 3 hours
EXTEND_LIFETIME_SECONDS = 3600   # +1 hour if promising
CHECK_INTERVAL_SECONDS = 300     # every 5 min

# In-memory token cache
token_cache: Dict[str, dict] = {}


def load_cache():
    """
    Load cache from disk into memory.
    """
    global token_cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                token_cache = json.load(f)
                print(f"[CACHE] Loaded {len(token_cache)} tokens from disk.")
        except Exception as e:
            print(f"[ERROR] Failed to load token cache: {e}")
            token_cache = {}
    else:
        token_cache = {}


def save_cache():
    """
    Save current token cache to disk.
    """
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(token_cache, f)
    except Exception as e:
        print(f"[ERROR] Failed to save token cache: {e}")


def add_token_if_new(mint: str, token_data: dict):
    """
    Add token to cache only if new. Update last_seen if already present.
    """
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
    """
    Mark token as rechecked. Extend lifetime if signal is positive.
    """
    if mint not in token_cache:
        return
    token_cache[mint]["last_checked"] = int(time.time())
    if signal_strength > 0:
        token_cache[mint]["expires_at"] = int(time.time()) + EXTEND_LIFETIME_SECONDS
        print(f"[CACHE] Token {mint} extended due to positive signal.")
    save_cache()


def get_due_for_check(interval: int = CHECK_INTERVAL_SECONDS):
    """
    Get tokens that haven't been rechecked in the last `interval` seconds.
    """
    now = int(time.time())
    return [
        {"address": mint, "data": token["data"]}
        for mint, token in token_cache.items()
        if now - token.get("last_checked", 0) >= interval
    ]


def get_ready_for_purge():
    """
    Get tokens whose lifetime has expired.
    """
    now = int(time.time())
    return [mint for mint, token in token_cache.items() if now >= token.get("expires_at", 0)]


def remove_token(mint: str):
    """
    Remove a token from the cache.
    """
    if mint in token_cache:
        del token_cache[mint]
        save_cache()


def cleanup_expired_tokens():
    """
    Remove all tokens that have expired.
    """
    to_remove = get_ready_for_purge()
    for mint in to_remove:
        print(f"[CACHE] Removing expired token {mint}")
        remove_token(mint)


# Load on module import
load_cache()



