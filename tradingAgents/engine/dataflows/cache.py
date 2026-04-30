"""简易文件缓存 — 减少 API 调用频率"""
import json
import os
from datetime import datetime
from typing import Optional


class DataCache:
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _key_path(self, key: str) -> str:
        safe = key.replace("/", "_").replace(":", "_")
        return os.path.join(self.cache_dir, f"{safe}.json")

    def get(self, key: str, max_age_seconds: int = 300) -> Optional[dict]:
        path = self._key_path(key)
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            data = json.load(f)
        age = (datetime.now() - datetime.fromisoformat(data["ts"])).total_seconds()
        if age > max_age_seconds:
            return None
        return data["value"]

    def set(self, key: str, value: dict):
        path = self._key_path(key)
        with open(path, "w") as f:
            json.dump({"ts": datetime.now().isoformat(), "value": value}, f)
