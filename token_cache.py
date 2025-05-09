
import time
import json
import threading
import os  # ✅ required for file existence and path handling
from typing import Dict

CACHE_FILE = "tracked_tokens.json"
LOCK = threading.Lock()

class TokenState:
    def __init__(self, address: str, created_at: float = None):
        self.address = address
        self.first_seen = created_at or time.time()
        self.last_checked = 0
        self.retry_count = 0
        self.promoted = False
        self.last_signal_strength = 0

    def to_dict(self):
        return {
            "address": self.address,
            "first_seen": self.first_seen,
            "last_checked": self.last_checked,
            "retry_count": self.retry_count,
            "promoted": self.promoted,
            "last_signal_strength": self.last_signal_strength
        }

    @staticmethod
    def from_dict(data: dict):
        token = TokenState(data["address"], data["first_seen"])
        token.last_checked = data.get("last_checked", 0)
        token.retry_count = data.get("retry_count", 0)
        token.promoted = data.get("promoted", False)
        token.last_signal_strength = data.get("last_signal_strength", 0)
        return token

class TokenCache:
    def __init__(self):
        self.tokens: Dict[str, TokenState] = {}
        self.load_cache()

    def load_cache(self):
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                try:
                    raw = json.load(f)
                    self.tokens = {
                        k: TokenState.from_dict(v)
                        for k, v in raw.items()
                    }
                    print(f"[CACHE] Loaded {len(self.tokens)} tokens from disk")
                except Exception as e:
                    print(f"[ERROR] Failed to load cache: {e}")

    def save_cache(self):
        with LOCK:
            with open(CACHE_FILE, "w") as f:
                json.dump({
                    k: v.to_dict()
                    for k, v in self.tokens.items()
                }, f, indent=2)

    def add_token(self, address: str):
        with LOCK:
            if address not in self.tokens:
                self.tokens[address] = TokenState(address)
                self.save_cache()

    def update_check(self, address: str, signal_strength: int = 0):
        with LOCK:
            if address in self.tokens:
                token = self.tokens[address]
                token.last_checked = time.time()
                token.retry_count += 1
                token.last_signal_strength = signal_strength
                self.save_cache()

    def promote_to_cache(self, address: str):
        with LOCK:
            if address in self.tokens:
                self.tokens[address].promoted = True
                self.save_cache()

    def get_due_for_check(self, max_age: int = 180, interval: int = 60):
        """Returns tokens needing recheck."""
        now = time.time()
        return [
            token for token in self.tokens.values()
            if (now - token.last_checked >= interval) and (now - token.first_seen < max_age * 60)
        ]

    def get_ready_for_purge(self, max_lifetime: int = 3 * 3600):
        """Returns tokens ready for purge due to inactivity."""
        now = time.time()
        return [
            k for k, v in self.tokens.items()
            if (now - v.first_seen > max_lifetime)
            and v.last_signal_strength < 1
        ]

    def remove_token(self, address: str):
        with LOCK:
            if address in self.tokens:
                del self.tokens[address]
                self.save_cache()


# Example usage (for local testing only):
if __name__ == "__main__":
    cache = TokenCache()
    cache.add_token("abcd1234")
    print("Check:", cache.get_due_for_check())
