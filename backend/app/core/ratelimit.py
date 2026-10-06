# Tiny in-memory sliding-window limiter. One process only.
# (With 2+ servers, move the counters to Redis.)
import time
from collections import defaultdict, deque
from fastapi import HTTPException, Request

_hits: dict[str, deque] = defaultdict(deque)


def hit(key: str, max_calls: int, window_s: int) -> None:
    now = time.monotonic()
    q = _hits[key]
    while q and now - q[0] > window_s:
        q.popleft()
    if len(q) >= max_calls:
        raise HTTPException(429, "Too many requests. Please try again later.")
    q.append(now)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
