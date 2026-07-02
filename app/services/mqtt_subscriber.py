import asyncio
import json
import logging
from typing import Any

from app.services.notifications import notification_broker

logger = logging.getLogger(__name__)


class MqttSubscriberService:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def _on_message(self, client, userdata, message) -> None:
        topic = message.topic
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except Exception:
            payload = {"data": message.payload.decode("utf-8", errors="ignore")}

        loop = self._loop or asyncio.get_running_loop()
        if loop.is_running():
            loop.call_soon_threadsafe(
                lambda: asyncio.create_task(notification_broker.publish(payload, topic=topic))
            )


mqtt_subscriber_service = MqttSubscriberService()
