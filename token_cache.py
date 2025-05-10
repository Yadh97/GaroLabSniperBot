# token_cache.py

import json
import os
import time
from typing import Dict

CACHE_FILE = "token_cache.json"
MAX_LIFETIME_SECONDS = 3 * 3600  # 3 hours
EXTEND_LIFETIME_SECONDS = 300   # 5 minutes
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
            "last_seen": now
        }
        save_cache()
    else:
        token_cache[mint]["last_seen"] = now
        save_cache()

def cleanup_expired_tokens():
    now = int(time.time())
    to_delete = []
    for mint, entry in token_cache.items():
        if now - entry["last_seen"] > MAX_LIFETIME_SECONDS:
            print(f"[CACHE] Removing expired token {mint}")
            to_delete.append(mint)
    for mint in to_delete:
        del token_cache[mint]
    if to_delete:
        save_cache()

load_cache()
