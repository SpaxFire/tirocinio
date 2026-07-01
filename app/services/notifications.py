import asyncio
import html
import json
from typing import Any


class NotificationBroker:
    def __init__(self) -> None:
        self._subscribers: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self._history: list[dict[str, Any]] = []
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
            self._history.append(event)
            subscribers = list(self._subscribers.items())

        for _, queue in subscribers:
            await queue.put(event)

    def get_history(self) -> list[dict[str, Any]]:
        return list(self._history)

    def clear(self) -> None:
        self._history.clear()

    def build_post_created_html(self, payload: dict[str, Any]) -> str:
        author = html.escape(str(payload.get("author", "qualcuno")))
        content = html.escape(str(payload.get("content", "")))
        preview = content[:140]
        if len(content) > 140:
            preview = f"{preview}..."
        return (

            '<div class="msg-notification"'
            'hx-on::load="setTimeout(() => event.target.remove(), 4000)"'
            'hx-get="notifications" hx-target="#main-content" hx-swap="innerHTML" hx-push-url="true">'
            f'<div>Nuovo post da {author}:</div>'
            f'<div class="text-sm text-slate-900">{preview}</div>'
            '</div>'
        )


notification_broker = NotificationBroker()
