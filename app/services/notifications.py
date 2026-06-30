import asyncio
import html
import json
from typing import Any


class NotificationBroker:
    def __init__(self) -> None:
        self._subscribers: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self) -> tuple[str, asyncio.Queue[dict[str, Any]]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        subscriber_id = f"sub-{id(queue)}"
        async with self._lock:
            self._subscribers[subscriber_id] = queue
        return subscriber_id, queue

    async def unsubscribe(self, subscriber_id: str) -> None:
        async with self._lock:
            self._subscribers.pop(subscriber_id, None)

    async def publish(self, payload: dict[str, Any], topic: str = "posts.created") -> None:
        event = {
            "topic": topic,
            "payload": payload,
        }
        async with self._lock:
            subscribers = list(self._subscribers.items())

        for _, queue in subscribers:
            await queue.put(event)

    def build_post_created_html(self, payload: dict[str, Any]) -> str:
        author = html.escape(str(payload.get("author", "qualcuno")))
        content = html.escape(str(payload.get("content", "")))
        preview = content[:140]
        if len(content) > 140:
            preview = f"{preview}..."
        return (
            '<div class="msg-notification transition-all duration-300"'
            'hx-on::load="setTimeout(() => event.target.remove(), 4000)">'
            f'<div class="font-semibold text-slate-900">Nuovo post da {author}:</div>'
            f'<div>{preview}</div>'
            '</div>'
        )


notification_broker = NotificationBroker()
