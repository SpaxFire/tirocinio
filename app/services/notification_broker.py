import asyncio
import html
import json
from typing import Any

# Classe per la gestione del broker di notifiche, che mantiene lo storico delle notifiche e gestisce gli abbonati
class NotificationBroker:
    def __init__(self) -> None:
        self._subscribers: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self._history: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()

    # Iscrive un nuovo abbonato e restituisce l'ID dell'abbonato e la coda delle notifiche
    async def subscribe(self) -> tuple[str, asyncio.Queue[dict[str, Any]]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        subscriber_id = f"sub-{id(queue)}"
        async with self._lock:
            self._subscribers[subscriber_id] = queue
        return subscriber_id, queue

    async def unsubscribe(self, subscriber_id: str) -> None:
        async with self._lock:
            self._subscribers.pop(subscriber_id, None)

    # Pubblica una notifica a tutti gli abbonati e la aggiunge allo storico
    async def publish(self, payload: dict[str, Any], topic: str = "notifications.created") -> None:
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

    # Restituisce i dettagli della notifica in base al payload ricevuto, formattando il titolo e il contenuto
    def get_notification_details(self, payload: dict[str, Any]) -> dict[str, Any]:
        event_type = payload.get("type", "post_created")
        author = str(payload.get("author", "qualcuno"))
        content = str(payload.get("content", ""))
        preview = content[:140]
        if len(content) > 140:
            preview = f"{preview}..."
        post_id = payload.get("post_id")

        if event_type == "post_liked":
            title = f"{author} ha messo like a"
            fallback = "Ha lasciato un like"
        elif event_type == "post_commented":
            title = f"{author} ha commentato"
            fallback = "Ha lasciato un commento"
        else:
            title = f"Nuovo post da {author}"
            fallback = "Nuovo contenuto disponibile"

        return {
            "type": event_type,
            "title": title,
            "content": preview or fallback,
            "post_id": post_id,
            "author": author,
        }

    # Costruisce l'HTML della notifica in base al payload ricevuto, formattando il titolo, il contenuto e il link al post
    def build_notification_html(self, payload: dict[str, Any]) -> str:
        notification = self.get_notification_details(payload)
        
        item_type = notification.get("type", "post_created")
        item_author = html.escape(str(payload.get("author", "qualcuno")))
        item_content = html.escape(str(notification.get("content", "")))
        item_post_id = notification.get("post_id")

        if item_type == "post_liked":
            item_title = f"{item_author} ha messo like ad un post"
            tab_type = "likes"
        elif item_type == "post_commented":
            item_title = f"{item_author} ha commentato un post"
            tab_type = "comments"
        else:
            item_title = f"Nuovo post da {item_author}"
            tab_type = "posts"

        # Frammento per la lista (con hx-swap-oob) - Aggiungiamo 'notification-item' e 'data-tab'
        # Usiamo classi CSS per controllare la visibilità dinamica lato client
        list_element_html = (
            f'<div class="notification-item rounded-xl border border-slate-200 p-4 bg-slate-50 transition-all" data-tab="{tab_type}">'
            f'<div class="font-semibold text-slate-900">{item_title}</div>'
            f'<div class="mt-1 text-sm text-slate-600">{item_content}</div>'
            f'<a hx-get="/posts/{item_post_id}" hx-target="#main-content" hx-push-url="true" hx-swap="innerHTML" '
            f'class="mt-3 inline-flex items-center text-sm font-medium text-blue-600 hover:text-blue-700 cursor-pointer">'
            f'Vai al post</a>'
            f'</div>'
        )

        popup_title = html.escape(notification["title"])
        popup_preview = html.escape(notification["content"])

        # Il popup viene mostrato sempre. L'elemento della lista viene inserito.
        # Aggiungiamo un blocco OOB per eliminare il placeholder se la notifica appartiene alla tab corrente
        return (
            f'<div class="msg-notification" hx-on::load="setTimeout(() => event.target.remove(), 4000)" '
            f'hx-get="/notifications?tab={tab_type}" hx-target="#main-content" hx-swap="innerHTML" hx-push-url="true">'
            f'<div>{popup_title}</div>'
            f'<div class="text-sm text-slate-900">{popup_preview}</div>'
            f'</div>'
            f'<div id="notifications-list" hx-swap-oob="afterbegin:#notifications-list">'
            f'{list_element_html}'
            f'</div>'
            f'<div id="no-notifications" hx-swap-oob="delete"></div>' # <-- RIMUOVE IL PLACEHOLDER DAL DOM
        )

    def build_post_created_html(self, payload: dict[str, Any], notifications: list[dict[str, Any]] | None = None) -> str:
        return self.build_notification_html(payload, notifications)


notification_broker = NotificationBroker()
