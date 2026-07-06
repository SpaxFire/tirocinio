import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from app.core.config import templates
from app.core.security import get_current_active_user
from app.db import user as user_db
from app.schemas.user import UserInDB
from app.services.notification_broker import notification_broker

# file di rotte nelle notifiche, per la gestione della pagina delle notifiche e dello stream SSE
router = APIRouter(prefix="/notifications", tags=["notifications"])

# Rotta per la pagina delle notifiche, che mostra le notifiche filtrate in base al tipo (post, like, commenti) e all'utente loggato
@router.get("", response_class=HTMLResponse)
async def notifications_page(
    request: Request,
    user: UserInDB = Depends(get_current_active_user),
    hx_request: Annotated[str | None, Header()] = None,
):
    active_tab = request.query_params.get("tab", "posts").lower()
    if active_tab not in {"posts", "likes", "comments"}:
        active_tab = "posts"

    # Recupera lo storico delle notifiche dal broker di notifiche e filtra le notifiche in base al tipo e all'utente loggato
    events = notification_broker.get_history()
    notifications = []

    for event in reversed(events):
        payload = event.get("payload", {})
        event_type = payload.get("type", "post_created")
        if event_type not in {"post_created", "post_liked", "post_commented"}:
            continue

        if active_tab == "posts" and event_type != "post_created":
            continue
        if active_tab == "likes" and event_type != "post_liked":
            continue
        if active_tab == "comments" and event_type != "post_commented":
            continue

        author = payload.get("author")
        if not author or not user_db.is_following(user.id, author):
            continue

        # Costruisce i dettagli della notifica in base al payload ricevuto e li aggiunge alla lista delle notifiche da visualizzare
        notification = notification_broker.get_notification_details(payload)
        notifications.append(
            {
                "author": author,
                "content": notification["content"],
                "post_id": notification["post_id"],
                "title": notification["title"],
                "type": notification["type"],
            }
        )

    template = "notifications/partials/notifications_content.html" if hx_request else "notifications/notifications.html"
    return templates.TemplateResponse(
        template,
        {
            "request": request,
            "notifications": notifications,
            "user": user,
            "active_tab": active_tab,
        },
    )

# Rotta per lo stream SSE delle notifiche, che invia le notifiche in tempo reale al client
@router.get("/stream")
async def notifications_stream(
    request: Request,
    user: UserInDB = Depends(get_current_active_user),
):
    async def event_generator():
        # Iscrizione al broker di notifiche e ottenimento della coda delle notifiche
        subscriber_id, queue = await notification_broker.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break
                
                # Recupera l'evento dalla coda delle notifiche e filtra le notifiche in base al tipo e all'utente loggato
                event = await asyncio.wait_for(queue.get(), timeout=None)
                payload = event.get("payload", {})
                event_type = payload.get("type", "post_created")

                if event_type not in {"post_created", "post_liked", "post_commented"}:
                    continue

                author = payload.get("author")
                if not author or not user_db.is_following(user.id, author):
                    continue
                
                # Costruisce l'HTML della notifica e lo invia al client tramite SSE
                html_fragment = notification_broker.build_notification_html(payload)
                yield f"event: message\ndata: {html_fragment}\n\n"
        except asyncio.TimeoutError:
            yield "event: ping\ndata: {}\n\n"
        finally:
            await notification_broker.unsubscribe(subscriber_id)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
