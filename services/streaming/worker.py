"""Live observation pipeline worker.

Consumes ``weather.raw.v1`` from Redpanda, runs the processing pipeline and
persists observations plus incident clusters into PostgreSQL/PostGIS.

Run:
    python -m services.streaming.worker
"""
import asyncio
import signal
from typing import Optional

from apps.api.core.config import settings
from apps.api.core.logging import logger
from services.streaming.consumer import EventConsumer
from services.streaming.producer import producer


async def _wait_for_stop(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig_name in ("SIGINT", "SIGTERM"):
        try:
            loop.add_signal_handler(getattr(signal, sig_name), stop_event.set)
        except (NotImplementedError, RuntimeError):  # pragma: no cover - Windows
            pass
    await stop_event.wait()


async def main() -> None:
    stop_event = asyncio.Event()

    logger.info(
        "Starting observation pipeline worker",
        extra={
            "stream_mode": settings.STREAM_MODE,
            "topic": settings.KAFKA_TOPIC_RAW,
            "broker": settings.KAFKA_BOOTSTRAP_SERVERS,
            "database": settings.POSTGRES_DB,
        },
    )

    if settings.STREAM_MODE == "redpanda":
        await producer.start()

    consumer = EventConsumer()
    worker_task = asyncio.create_task(consumer.run(stop_event))
    await _wait_for_stop(stop_event)

    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    await producer.stop()
    logger.info("Observation pipeline worker stopped")


def run() -> None:
    try:
        asyncio.run(main())
    except KeyboardInterrupt:  # pragma: no cover
        pass


if __name__ == "__main__":
    run()
