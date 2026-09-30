import asyncio
import json
from typing import Any, Dict, Optional

from aiokafka.structs import TopicPartition

from apps.api.core.config import settings
from apps.api.core.logging import logger
from apps.api.db.session import SessionLocal
from services.processing.pipeline import pipeline_engine
from services.streaming.bus import stream_bus
from services.streaming.producer import producer


class EventConsumer:
    """
    Kafka / Stream Bus Event Consumer.

    Live mode (``STREAM_MODE=redpanda``) polls the real broker with manual
    offset commits and applies the documented failure policy:

    * malformed payloads            -> ``weather.dlq.v1`` (deterministic, no retry)
    * transient failures (e.g. DB)  -> bounded retry with backoff, then DLQ
    * success / duplicate suppressed -> offset committed

    Bus mode (``STREAM_MODE=bus``) keeps the deterministic in-memory
    subscription used by unit tests and demo replay (DEC-002).
    """

    def __init__(
        self,
        topic: Optional[str] = None,
        dlq_topic: Optional[str] = None,
        group_id: Optional[str] = None,
        max_retries: int = 3,
        retry_backoff_seconds: float = 0.5,
    ):
        self.topic = topic or settings.KAFKA_TOPIC_RAW
        self.dlq_topic = dlq_topic or settings.KAFKA_TOPIC_DLQ
        self.group_id = group_id or settings.KAFKA_CONSUMER_GROUP
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self._is_registered = False
        self.processed_count = 0
        self.dlq_count = 0

    # ------------------------------------------------------------------
    # Bus mode
    # ------------------------------------------------------------------
    def register(self):
        if not self._is_registered:
            stream_bus.subscribe(self.topic, self.handle_event)
            self._is_registered = True
            logger.info(f"[Consumer] Subscribed to topic {self.topic}")

    # ------------------------------------------------------------------
    # Shared processing logic
    # ------------------------------------------------------------------
    async def handle_event(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        payload = envelope.get("payload") if isinstance(envelope, dict) and "payload" in envelope else envelope

        db = SessionLocal()
        try:
            result = pipeline_engine.process_raw_observation(payload, db)
            self.processed_count += 1
            logger.info(f"[Consumer] Processed event from {self.topic}: {result['status']}")
            return result
        except ValueError as val_err:
            # Deterministic validation failure: never retried, always dead-lettered.
            logger.warning(f"[Consumer] Malformed event on {self.topic}: {val_err}")
            await self.send_to_dlq(payload, str(val_err))
            return {"status": "MALFORMED", "error": str(val_err), "is_duplicate": False}
        except Exception as exc:
            db.rollback()
            # Infrastructure/unknown failure: caller decides on retry.
            raise exc
        finally:
            db.close()

    async def send_to_dlq(self, payload: Dict[str, Any], error: str) -> None:
        entry = {
            "origin_topic": self.topic,
            "message": payload,
            "error": error,
        }
        self.dlq_count += 1
        if settings.STREAM_MODE == "redpanda":
            await producer.publish(topic=self.dlq_topic, key=None, payload=entry)
            logger.error(f"[Consumer] Routed failed event to {self.dlq_topic}: {error}")
        else:
            await stream_bus.send_to_dlq(self.topic, payload, error)

    # ------------------------------------------------------------------
    # Live Redpanda loop
    # ------------------------------------------------------------------
    async def run(self, stop_event: Optional[asyncio.Event] = None) -> None:
        if settings.STREAM_MODE != "redpanda":
            self.register()
            logger.info("[Consumer] STREAM_MODE=bus — waiting for in-memory events.")
            while stop_event is None or not stop_event.is_set():
                await asyncio.sleep(0.25)
            return

        backoff = 1.0
        while stop_event is None or not stop_event.is_set():
            try:
                await self._consume_loop(stop_event)
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - infrastructure failures must not kill the worker
                logger.error(
                    f"[Consumer] Stream loop failed: {exc}. Retrying in {backoff:.1f}s "
                    "(uncommitted offsets will be redelivered)"
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    async def _consume_loop(self, stop_event: Optional[asyncio.Event]) -> None:
        from aiokafka import AIOKafkaConsumer

        consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=self.group_id,
            client_id=f"{settings.KAFKA_CLIENT_ID}-consumer",
            enable_auto_commit=False,
            auto_offset_reset=settings.KAFKA_AUTO_OFFSET_RESET,
        )
        await consumer.start()
        logger.info(
            f"[Consumer] Live consumer started on {self.topic} "
            f"(group={self.group_id}, broker={settings.KAFKA_BOOTSTRAP_SERVERS})"
        )
        try:
            while stop_event is None or not stop_event.is_set():
                batch = await consumer.getmany(timeout_ms=1000, max_records=64)
                for _tp, messages in batch.items():
                    for message in messages:
                        await self._process_message(consumer, message)
        finally:
            await consumer.stop()
            logger.info("[Consumer] Live consumer stopped")

    async def _process_message(self, consumer, message) -> None:
        payload: Any
        try:
            payload = json.loads(message.value.decode("utf-8")) if message.value else None
        except Exception as decode_exc:
            await self._dead_letter(consumer, message, None, f"Undecodable message: {decode_exc}")
            return

        if not isinstance(payload, dict):
            await self._dead_letter(consumer, message, payload, "Message value is not a JSON object")
            return

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                await self.handle_event(payload)
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                logger.warning(
                    f"[Consumer] Processing failed (attempt {attempt}/{self.max_retries}) "
                    f"offset={message.offset}: {exc}"
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_backoff_seconds * attempt)

        if last_error is not None:
            await self._dead_letter(
                consumer,
                message,
                payload,
                f"Processing failed after {self.max_retries} attempts: {last_error}",
            )
            return

        await consumer.commit({TopicPartition(message.topic, message.partition): message.offset + 1})

    async def _dead_letter(self, consumer, message, payload: Any, error: str) -> None:
        try:
            await self.send_to_dlq(payload, error)
        except Exception as dlq_exc:
            # Broker also unavailable: keep the offset uncommitted so the message
            # is redelivered instead of being silently dropped.
            logger.error(f"[Consumer] DLQ publish failed, offset will be retried: {dlq_exc}")
            await asyncio.sleep(self.retry_backoff_seconds)
            raise
        await consumer.commit({TopicPartition(message.topic, message.partition): message.offset + 1})


consumer = EventConsumer()
