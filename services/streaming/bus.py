import asyncio
from typing import Dict, List, Any, Callable, Awaitable
from collections import defaultdict
from apps.api.core.logging import logger


class StreamEventBus:
    """
    Deterministic In-Memory Replay and Stream Bus.
    Conforms to DEC-002: Deterministic replay and local testing fallback
    when Redpanda broker is not running.
    """

    def __init__(self):
        self._topics: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._subscribers: Dict[str, List[Callable[[Dict[str, Any]], Awaitable[None]]]] = defaultdict(list)
        self._dlq: List[Dict[str, Any]] = []

    def subscribe(self, topic: str, handler: Callable[[Dict[str, Any]], Awaitable[None]]):
        self._subscribers[topic].append(handler)

    async def publish(self, topic: str, message: Dict[str, Any]):
        self._topics[topic].append(message)
        logger.info(f"[StreamBus] Published message to {topic} (Key: {message.get('key', 'none')})")

        # Notify active consumers
        handlers = self._subscribers.get(topic, [])
        for handler in handlers:
            try:
                await handler(message)
            except Exception as exc:
                logger.error(f"[StreamBus] Consumer handler failed on topic {topic}: {exc}")
                await self.send_to_dlq(topic, message, str(exc))

    async def send_to_dlq(self, origin_topic: str, message: Dict[str, Any], error: str):
        dlq_entry = {
            "origin_topic": origin_topic,
            "message": message,
            "error": error,
        }
        self._dlq.append(dlq_entry)
        self._topics["weather.dlq.v1"].append(dlq_entry)
        logger.warning(f"[StreamBus] Routed malformed/failed event to weather.dlq.v1: {error}")

    def get_messages(self, topic: str) -> List[Dict[str, Any]]:
        return list(self._topics.get(topic, []))

    def get_dlq_messages(self) -> List[Dict[str, Any]]:
        return list(self._dlq)

    def clear(self):
        self._topics.clear()
        self._dlq.clear()


stream_bus = StreamEventBus()
