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

    def build_post_created_html(self, payload: dict[str, Any], notifications: list[dict[str, Any]] | None = None) -> str:
        author = html.escape(str(payload.get("author", "qualcuno")))
        content = html.escape(str(payload.get("content", "")))
        preview = content[:140]
        if len(content) > 140:
            preview = f"{preview}..."
        post_id = payload.get("post_id")
        post_link = f'/posts/{post_id}' if post_id else '/notifications'

        items = notifications or []
        if not any(item.get("post_id") == post_id for item in items):
            items = [
                {
                    "author": payload.get("author"),
                    "content": preview,
                    "post_id": post_id,
                },
                *items,
            ]

        rendered_items = []
        for item in items:
            item_author = html.escape(str(item.get("author", "qualcuno")))
            item_content = html.escape(str(item.get("content", "")))
            item_preview = item_content[:140]
            if len(item_content) > 140:
                item_preview = f"{item_preview}..."
            item_post_id = item.get("post_id")
            rendered_items.append(
                '<div class="rounded-xl border border-slate-200 p-4 bg-slate-50">'
                '<div class="font-semibold text-slate-900">'
                f'Nuovo post da {item_author}'
                '</div>'
                f'<div class="mt-1 text-sm text-slate-600">{item_preview}</div>'
                f'<a hx-get="/posts/{item_post_id}" hx-target="#main-content" hx-push-url="true" hx-swap="innerHTML"'
                'class="mt-3 inline-flex items-center text-sm font-medium text-blue-600 hover:text-blue-700 cursor-pointer">'
                'Vai al post'
                '</a>'
                '</div>'
            )

        list_html = ''.join(rendered_items)

        return (
            '<div class="msg-notification"'
            'hx-on::load="setTimeout(() => event.target.remove(), 4000)"'
            'hx-get="notifications" hx-target="#main-content" hx-swap="innerHTML" hx-push-url="true">'
            f'<div>Nuovo post da {author}:</div>'
            f'<div class="text-sm text-slate-900">{preview}</div>'
            '</div>'
            '<div id="notifications-list" hx-swap-oob="afterbegin:#notifications-list">'
            f'{list_html}'
            '</div>'
        )


notification_broker = NotificationBroker()
