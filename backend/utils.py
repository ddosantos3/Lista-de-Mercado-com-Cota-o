import json
import logging
import os
import time
from typing import Any, Dict, Optional


def setup_logging() -> logging.Logger:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=level, format="%(message)s")
    return logging.getLogger("cotador")


logger = setup_logging()


def log_json(event: str, **fields: Any) -> None:
    rec: Dict[str, Any] = {"event": event, **fields}
    try:
        logging.getLogger("cotador").info(json.dumps(rec, ensure_ascii=False))
    except Exception:
        logging.getLogger("cotador").info(str(rec))


class RateLimiter:
    """In-memory sliding window limiter (best-effort).

    For production, prefer Redis-based rate limiting.
    """

    def __init__(self, max_requests: int, per_seconds: int) -> None:
        self.max_requests = max_requests
        self.per_seconds = per_seconds
        self._hits: Dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        window_start = now - self.per_seconds
        hits = self._hits.setdefault(key, [])
        # Drop old hits
        i = 0
        for i, ts in enumerate(hits):
            if ts >= window_start:
                break
        if hits and hits[0] < window_start:
            hits[:] = hits[i:]
        # Allow if under limit
        if len(hits) < self.max_requests:
            hits.append(now)
            return True
        return False

