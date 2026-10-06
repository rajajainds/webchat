# Keeps track of open WebSockets. One user can have many (phone + laptop).
from collections import defaultdict
from fastapi import WebSocket


class Manager:
    def __init__(self) -> None:
        self.conns: dict[str, set[WebSocket]] = defaultdict(set)

    def add(self, uid: str, ws: WebSocket) -> None:
        self.conns[uid].add(ws)

    def remove(self, uid: str, ws: WebSocket) -> None:
        self.conns[uid].discard(ws)
        if not self.conns[uid]:
            del self.conns[uid]

    async def send_user(self, uid: str, event: dict) -> None:
        for ws in list(self.conns.get(uid, ())):
            try:
                await ws.send_json(event)
            except Exception:  # dead socket: drop it
                self.conns[uid].discard(ws)


manager = Manager()  # one shared instance (single server; Redis pub/sub for many)
