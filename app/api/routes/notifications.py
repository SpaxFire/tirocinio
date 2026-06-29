import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.services.notifications import notification_broker

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/stream")
async def notifications_stream(request: Request):
    async def event_generator():
        subscriber_id, queue = await notification_broker.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break

                event = await asyncio.wait_for(queue.get(), timeout=30)
                html_fragment = notification_broker.build_post_created_html(event["payload"])
                yield f"event: message\ndata: {html_fragment}\n\n"
        except asyncio.TimeoutError:
            yield "event: ping\ndata: {}\n\n"
        finally:
            await notification_broker.unsubscribe(subscriber_id)
        print("Client disconnected from notifications stream")

    return StreamingResponse(event_generator(), media_type="text/event-stream")
