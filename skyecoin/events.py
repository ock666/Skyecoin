import json
import time
import asyncio
import logging
from typing import Any
from collections import deque

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self, max_history: int = 200):
        self._subscribers: list["EventSubscriber"] = []
        self._history: deque[dict] = deque(maxlen=max_history)
        self._lock = asyncio.Lock()

    async def subscribe(self) -> "EventSubscriber":
        sub = EventSubscriber(self)
        async with self._lock:
            self._subscribers.append(sub)
        return sub

    async def unsubscribe(self, sub: "EventSubscriber"):
        async with self._lock:
            if sub in self._subscribers:
                self._subscribers.remove(sub)

    async def publish(self, event_type: str, data: dict[str, Any]):
        event = {
            "type": event_type,
            "data": data,
            "timestamp": time.time(),
        }
        self._history.append(event)
        dead = []
        for sub in self._subscribers:
            try:
                await sub.queue.put(event)
            except Exception:
                dead.append(sub)
        for sub in dead:
            await self.unsubscribe(sub)

    async def get_history(self, since: float = 0, limit: int = 50) -> list[dict]:
        return [e for e in self._history if e["timestamp"] > since][-limit:]

    async def broadcast(self):
        while self._subscribers:
            await self.publish("heartbeat", {"peers": len(self._subscribers)})
            await asyncio.sleep(30)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


class EventSubscriber:
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=500)

    async def close(self):
        await self.bus.unsubscribe(self)


event_bus = EventBus()
