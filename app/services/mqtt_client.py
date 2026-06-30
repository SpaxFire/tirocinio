import asyncio
import json
import logging
import os
from typing import Any

from app.services.notifications import notification_broker

try:
    import paho.mqtt.client as mqtt
except ImportError:  # pragma: no cover - optional dependency
    mqtt = None

logger = logging.getLogger(__name__)


class MqttNotificationClient:
    def __init__(self) -> None:
        self._host = os.getenv("MQTT_BROKER_HOST", "localhost")
        self._port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
        self._username = os.getenv("MQTT_USERNAME")
        self._password = os.getenv("MQTT_PASSWORD")
        self._topic = os.getenv("MQTT_TOPIC", "posts.created")
        self._client = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._connected = False

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def start(self) -> bool:
        if mqtt is None:
            logger.warning("paho-mqtt not installed; falling back to local notifications")
            return False

        if self._client is not None:
            return True

        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            client.on_connect = self._on_connect
            client.on_disconnect = self._on_disconnect
            client.on_message = self._on_message

            if self._username and self._password:
                client.username_pw_set(self._username, self._password)

            client.connect_async(self._host, self._port, 60)
            client.loop_start()
            self._client = client
            return True
        except Exception as exc:  # pragma: no cover - depends on broker availability
            logger.warning("MQTT connection failed: %s", exc)
            return False

    def stop(self) -> None:
        if self._client is not None:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
            self._connected = False

    def publish(self, payload: dict[str, Any], topic: str | None = None) -> None:
        target_topic = topic or self._topic
        if self._client is not None and self._connected:
            try:
                self._client.publish(target_topic, json.dumps(payload), qos=1, retain=False)
                return
            except Exception as exc:  # pragma: no cover - depends on broker availability
                logger.warning("MQTT publish failed: %s", exc)

        loop = self._loop or asyncio.get_running_loop()
        loop.create_task(notification_broker.publish(payload, topic=target_topic))

    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        self._connected = True
        try:
            client.subscribe(self._topic, qos=1)
        except Exception as exc:  # pragma: no cover - broker specific
            logger.warning("MQTT subscribe failed: %s", exc)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties=None) -> None:
        self._connected = False

    def _on_message(self, client, userdata, message) -> None:
        topic = message.topic
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except Exception:
            payload = {"data": message.payload.decode("utf-8", errors="ignore")}

        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(notification_broker.publish(payload, topic=topic))
            )


mqtt_notification_client = MqttNotificationClient()
