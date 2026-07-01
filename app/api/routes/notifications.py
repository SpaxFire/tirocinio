import asyncio

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.core.security import get_current_active_user
from app.db import user as user_db
from app.schemas.user import UserInDB
from app.services.notifications import notification_broker

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/stream")
async def notifications_stream(
    request: Request,
    user: UserInDB = Depends(get_current_active_user),
):
    async def event_generator():
        subscriber_id, queue = await notification_broker.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break

                event = await asyncio.wait_for(queue.get(), timeout=30)
                payload = event.get("payload", {})

                if payload.get("type") == "post_created":
                    author = payload.get("author")
                    if not author or not user_db.is_following(user.id, author):
                        continue

                html_fragment = notification_broker.build_post_created_html(payload)
                yield f"event: message\ndata: {html_fragment}\n\n"
        except asyncio.TimeoutError:
            yield "event: ping\ndata: {}\n\n"
        finally:
            await notification_broker.unsubscribe(subscriber_id)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
