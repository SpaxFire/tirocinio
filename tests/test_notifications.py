import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.notifications import NotificationBroker


@pytest.mark.anyio
async def test_notification_broker_delivers_payload_to_subscribers():
    broker = NotificationBroker()
    subscriber_id, queue = await broker.subscribe()

    try:
        await broker.publish(
            {
                "type": "post_created",
                "author": "alice",
                "content": "Nuovo post di prova",
            }
        )

        event = await asyncio.wait_for(queue.get(), timeout=1)
        assert event["payload"]["author"] == "alice"
        assert "Nuovo post di prova" in event["payload"]["content"]
    finally:
        await broker.unsubscribe(subscriber_id)


def test_notifications_stream_endpoint_returns_sse_headers():
    client = TestClient(app)

    with client.stream("GET", "/notifications/stream") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
