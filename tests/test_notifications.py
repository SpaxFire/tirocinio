import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.mqtt_client import mqtt_notification_client
from app.services.notifications import NotificationBroker, notification_broker


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


@pytest.mark.anyio
async def test_mqtt_publish_does_not_duplicate_when_client_is_connected():
    subscriber_id, queue = await notification_broker.subscribe()
    original_client = mqtt_notification_client._client
    original_connected = mqtt_notification_client._connected
    original_loop = mqtt_notification_client._loop

    class FakeClient:
        def __init__(self) -> None:
            self.published = []

        def publish(self, topic, payload, qos=1, retain=False):
            self.published.append((topic, payload, qos, retain))

    fake_client = FakeClient()
    mqtt_notification_client._client = fake_client
    mqtt_notification_client._connected = True
    mqtt_notification_client._loop = asyncio.get_running_loop()

    try:
        payload = {"type": "post_created", "content": "solo una notifica"}
        mqtt_notification_client.publish(payload)
        mqtt_notification_client._on_message(None, None, type("Msg", (), {"topic": "posts.created", "payload": json.dumps(payload).encode("utf-8")})())

        event = await asyncio.wait_for(queue.get(), timeout=1)
        assert event["payload"]["content"] == "solo una notifica"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.1)
    finally:
        mqtt_notification_client._client = original_client
        mqtt_notification_client._connected = original_connected
        mqtt_notification_client._loop = original_loop
        await notification_broker.unsubscribe(subscriber_id)
