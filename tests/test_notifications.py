import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import get_current_active_user
from app.schemas.user import UserInDB
from app.services.mqtt_client import mqtt_notification_client
from app.services.mqtt_subscriber import MqttSubscriberService
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

    def override_current_user():
        return UserInDB(
            id="user-1",
            username="alice",
            email="alice@example.com",
            password_hash="hash",
            role="USER",
            bio=None,
            profile_image=None,
            created_at=None,
            is_active=True,
        )

    app.dependency_overrides[get_current_active_user] = override_current_user
    try:
        with client.stream("GET", "/notifications/stream") as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
    finally:
        app.dependency_overrides.clear()


def test_notification_html_includes_popup_and_oob_target_for_live_page_updates():
    html = notification_broker.build_post_created_html(
        {
            "type": "post_created",
            "author": "bob",
            "content": "Contenuto del post",
            "post_id": "post-123",
        }
    )

    assert 'class="msg-notification"' in html
    assert 'hx-on::load' in html
    assert 'hx-swap-oob="afterbegin:#notifications-list"' in html
    assert "Vai al post" in html


def test_notification_html_keeps_previous_history_in_live_list_updates():
    html = notification_broker.build_post_created_html(
        {
            "type": "post_created",
            "author": "bob",
            "content": "Nuova notifica",
            "post_id": "post-123",
        },
        notifications=[
            {"author": "alice", "content": "Vecchia notifica", "post_id": "post-1"},
            {"author": "bob", "content": "Nuova notifica", "post_id": "post-123"},
        ],
    )

    assert "Vecchia notifica" in html
    assert "Nuova notifica" in html


def test_notifications_page_lists_received_notifications_with_post_links():
    client = TestClient(app)
    notification_broker.clear()

    def override_current_user():
        return UserInDB(
            id="user-1",
            username="alice",
            email="alice@example.com",
            password_hash="hash",
            role="USER",
            bio=None,
            profile_image=None,
            created_at=None,
            is_active=True,
        )

    app.dependency_overrides[get_current_active_user] = override_current_user
    try:
        asyncio.run(
            notification_broker.publish(
                {
                    "type": "post_created",
                    "author": "bob",
                    "content": "Contenuto del post",
                    "post_id": "post-123",
                }
            )
        )

        with patch("app.api.routes.notifications.user_db.is_following", return_value=True):
            response = client.get("/notifications")

        assert response.status_code == 200
        assert "Vai al post" in response.text
        assert "/posts/post-123" in response.text
    finally:
        app.dependency_overrides.clear()
        notification_broker.clear()


def test_notifications_page_filters_likes_and_comments_from_followed_users():
    client = TestClient(app)
    notification_broker.clear()

    def override_current_user():
        return UserInDB(
            id="user-1",
            username="alice",
            email="alice@example.com",
            password_hash="hash",
            role="USER",
            bio=None,
            profile_image=None,
            created_at=None,
            is_active=True,
        )

    app.dependency_overrides[get_current_active_user] = override_current_user
    try:
        asyncio.run(
            notification_broker.publish(
                {
                    "type": "post_liked",
                    "author": "bob",
                    "content": "",
                    "post_id": "post-like-123",
                }
            )
        )
        asyncio.run(
            notification_broker.publish(
                {
                    "type": "post_commented",
                    "author": "carol",
                    "content": "Bellissimo post",
                    "post_id": "post-comment-123",
                }
            )
        )
        asyncio.run(
            notification_broker.publish(
                {
                    "type": "post_created",
                    "author": "dave",
                    "content": "Nuovo post",
                    "post_id": "post-created-123",
                }
            )
        )

        with patch("app.api.routes.notifications.user_db.is_following", return_value=True):
            likes_response = client.get("/notifications?tab=likes")
            comments_response = client.get("/notifications?tab=comments")
            posts_response = client.get("/notifications?tab=posts")

        assert likes_response.status_code == 200
        assert "ha messo like" in likes_response.text.lower()
        assert "post-like-123" in likes_response.text

        assert comments_response.status_code == 200
        assert "ha commentato" in comments_response.text.lower()
        assert "Bellissimo post" in comments_response.text

        assert posts_response.status_code == 200
        assert "Nuovo post da" in posts_response.text
    finally:
        app.dependency_overrides.clear()
        notification_broker.clear()


@pytest.mark.anyio
async def test_notification_stream_filters_events_for_followed_users():
    subscriber_id, queue = await notification_broker.subscribe()

    try:
        with patch("app.api.routes.notifications.user_db.is_following", return_value=True):
            await notification_broker.publish(
                {"type": "post_created", "author": "bob", "content": "post visibile"}
            )
            event = await asyncio.wait_for(queue.get(), timeout=1)
            assert event["payload"]["content"] == "post visibile"
    finally:
        await notification_broker.unsubscribe(subscriber_id)


@pytest.mark.anyio
async def test_mqtt_subscriber_service_forwards_inbound_messages_to_notification_broker():
    subscriber_service = MqttSubscriberService()
    subscriber_service._loop = asyncio.get_running_loop()
    subscriber_id, queue = await notification_broker.subscribe()

    with patch("app.services.mqtt_subscriber.notification_broker.publish", new_callable=AsyncMock) as publish_mock:
        subscriber_service._on_message(
            None,
            None,
            type(
                "Msg",
                (),
                {"topic": "posts.created", "payload": json.dumps({"type": "post_created", "content": "hello"}).encode("utf-8")},
            )(),
        )
        await asyncio.sleep(0.01)

        publish_mock.assert_awaited_once()
        assert publish_mock.await_args.args[0]["content"] == "hello"

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
        mqtt_notification_client._on_message(
            None,
            None,
            type(
                "Msg",
                (),
                {"topic": "posts.created", "payload": json.dumps(payload).encode("utf-8")},
            )(),
        )

        event = await asyncio.wait_for(queue.get(), timeout=1)
        assert event["payload"]["content"] == "solo una notifica"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.1)
    finally:
        mqtt_notification_client._client = original_client
        mqtt_notification_client._connected = original_connected
        mqtt_notification_client._loop = original_loop
        await notification_broker.unsubscribe(subscriber_id)
