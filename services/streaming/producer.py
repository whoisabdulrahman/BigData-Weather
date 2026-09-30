import json
from typing import Dict, Any, List, Optional

from apps.api.core.config import settings
from apps.api.core.logging import logger
from services.streaming.bus import stream_bus


class StreamPublishError(RuntimeError):
    """Raised when a message could not be delivered to the configured transport.

    Live mode never silently degrades to the in-memory bus: an unavailable
    broker must surface as a clear failure so callers can retry or reject.
    """


class EventProducer:
    """
    Kafka / Redpanda Event Producer.

    Transport is selected from ``settings.STREAM_MODE``:
      * ``redpanda`` — live broker, hard failures via :class:`StreamPublishError`
      * ``bus`` — deterministic in-memory bus (unit tests, demo/replay, DEC-002)
    """

    def __init__(self, bootstrap_servers: Optional[str] = None):
        self.bootstrap_servers = bootstrap_servers or settings.KAFKA_BOOTSTRAP_SERVERS
        self._aiokafka_producer = None
        self._is_live_kafka_connected = False

    @property
    def mode(self) -> str:
        return settings.STREAM_MODE

    def _required_topics(self) -> List[str]:
        return [
            topic.strip()
            for topic in settings.KAFKA_TOPIC_BOOTSTRAP.split(",")
            if topic.strip()
        ]

    async def ensure_topics(self) -> List[str]:
        """Create the application topics when missing. Returns created topic names."""
        from aiokafka.admin import AIOKafkaAdminClient, NewTopic

        admin = AIOKafkaAdminClient(bootstrap_servers=self.bootstrap_servers)
        try:
            await admin.start()
            existing = set(await admin.list_topics())
            missing = [t for t in self._required_topics() if t not in existing]
            if missing:
                await admin.create_topics(
                    [NewTopic(t, num_partitions=1, replication_factor=1) for t in missing]
                )
                logger.info(f"[Producer] Bootstrapped topics: {missing}")
            else:
                logger.info(f"[Producer] Topics already present: {self._required_topics()}")
            return missing
        finally:
            try:
                await admin.close()
            except Exception:  # pragma: no cover - best effort cleanup
                pass

    async def start(self):
        if settings.STREAM_MODE != "redpanda":
            logger.info("[Producer] STREAM_MODE=bus — using deterministic in-memory stream bus.")
            return

        try:
            from aiokafka import AIOKafkaProducer

            producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                request_timeout_ms=5000,
                retry_backoff_ms=200,
            )
            await producer.start()
        except Exception as exc:
            self._is_live_kafka_connected = False
            self._aiokafka_producer = None
            logger.error(
                f"[Producer] Redpanda broker unavailable at {self.bootstrap_servers}: {exc}. "
                "Publishes will fail until the broker is reachable."
            )
            return

        self._aiokafka_producer = producer
        self._is_live_kafka_connected = True
        logger.info(f"[Producer] Connected to Redpanda cluster at {self.bootstrap_servers}")
        try:
            await self.ensure_topics()
        except Exception as exc:  # pragma: no cover - topic auto-creation is a fallback
            logger.warning(f"[Producer] Topic bootstrap failed (broker may auto-create): {exc}")

    async def publish(self, topic: str, key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        transport = "redpanda" if settings.STREAM_MODE == "redpanda" else "stream_bus"
        envelope = {
            "topic": topic,
            "key": key,
            "payload": payload,
            "transport": transport,
        }

        if settings.STREAM_MODE != "redpanda":
            await stream_bus.publish(topic, envelope)
            return envelope

        if not self._is_live_kafka_connected or self._aiokafka_producer is None:
            await self.start()

        if not self._is_live_kafka_connected or self._aiokafka_producer is None:
            raise StreamPublishError(
                f"Redpanda broker unavailable at {self.bootstrap_servers}; message to '{topic}' was not published."
            )

        try:
            await self._aiokafka_producer.send_and_wait(topic, value=payload, key=key)
        except Exception as exc:
            self._is_live_kafka_connected = False
            raise StreamPublishError(
                f"Failed to publish message to topic '{topic}': {exc}"
            ) from exc

        logger.info(f"[Producer] Published message to {topic} via Redpanda (key={key})")
        return envelope

    async def stop(self):
        if self._aiokafka_producer:
            try:
                await self._aiokafka_producer.stop()
            finally:
                self._aiokafka_producer = None
                self._is_live_kafka_connected = False


producer = EventProducer()
