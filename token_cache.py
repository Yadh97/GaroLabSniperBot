# Filename: token_cache.py

import json
import os
import time
from typing import Dict, List

class TokenCache:
    def __init__(self, cache_file: str = "token_cache.json"):
        self.cache_file = cache_file
        self.max_lifetime = 3 * 3600  # 3 hours
        self.extend_lifetime = 3600   # +1 hour if promising
        self.check_interval = 300     # 5 min
        self.cache: Dict[str, dict] = {}
        self.load()

    def load(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    self.cache = json.load(f)
                    print(f"[CACHE] Loaded {len(self.cache)} tokens from disk.")
            except Exception as e:
                print(f"[ERROR] Failed to load token cache: {e}")
                self.cache = {}

    def save(self):
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f)
        except Exception as e:
            print(f"[ERROR] Failed to save token cache: {e}")

    def add_token_if_new(self, mint: str, token_data: dict):
        now = int(time.time())
        if mint not in self.cache:
            print(f"[CACHE] Adding new token {mint} to cache.")
            self.cache[mint] = {
                "data": token_data,
                "created": now,
                "last_seen": now,
                "last_checked": 0,
                "expires_at": now + self.max_lifetime
            }
            self.save()
        else:
            self.cache[mint]["last_seen"] = now
            self.save()

    def update_check(self, mint: str, signal_strength: int = 0):
        if mint not in self.cache:
            return
        self.cache[mint]["last_checked"] = int(time.time())
        if signal_strength > 0:
            self.cache[mint]["expires_at"] = int(time.time()) + self.extend_lifetime
            print(f"[CACHE] Token {mint} extended due to positive signal.")
        self.save()

    def get_due_for_check(self, interval: int = None) -> List[dict]:
        interval = interval or self.check_interval
        now = int(time.time())
        return [
            {"address": mint, "data": token["data"]}
            for mint, token in self.cache.items()
            if now - token.get("last_checked", 0) >= interval
        ]

    def get_ready_for_purge(self) -> List[str]:
        now = int(time.time())
        return [mint for mint, token in self.cache.items() if now >= token.get("expires_at", 0)]

    def remove_token(self, mint: str):
        if mint in self.cache:
            del self.cache[mint]
            self.save()

    def cleanup_expired_tokens(self):
        expired = self.get_ready_for_purge()
        for mint in expired:
            print(f"[CACHE] Removing expired token {mint}")
            self.remove_token(mint)

    def should_process(self, mint: str) -> bool:
        return mint not in self.cache

    def mark_processed(self, mint: str):
        self.update_check(mint, signal_strength=1)

    def mark_filtered(self, mint: str):
        self.update_check(mint, signal_strength=0)
