import json
import os
import time
from typing import Dict

CACHE_FILE = "token_cache.json"
MAX_LIFETIME_SECONDS = 3 * 3600  # 3 hours
EXTEND_LIFETIME_SECONDS = 3600   # 1 hour
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
    if mint not in token_cache:
        return
    token_cache[mint]["last_checked"] = int(time.time())
    if signal_strength > 0:
        token_cache[mint]["expires_at"] = int(time.time()) + EXTEND_LIFETIME_SECONDS
        print(f"[CACHE] Token {mint} extended due to positive signal.")
    save_cache()

def get_due_for_check(interval: int = 300):
    now = int(time.time())
    return [
        {"address": mint, "data": token["data"]}
        for mint, token in token_cache.items()
        if now - token.get("last_checked", 0) >= interval
    ]

def get_ready_for_purge():
    now = int(time.time())
    return [mint for mint, token in token_cache.items() if now >= token.get("expires_at", 0)]

def remove_token(mint: str):
    if mint in token_cache:
        del token_cache[mint]
        save_cache()

def cleanup_expired_tokens():
    to_remove = get_ready_for_purge()
    for mint in to_remove:
        print(f"[CACHE] Removing expired token {mint}")
        remove_token(mint)

load_cache()


