"""Shared helpers for tests that exercise the live Docker infrastructure.

These helpers only talk to real services (PostgreSQL/PostGIS, Redpanda). Tests
that use them skip automatically when the infrastructure is not reachable.
"""
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]

LIVE_API_PORT = 8010
DEAD_BROKER_API_PORT = 8011
DEAD_DB_WORKER_PORT_NOTE = "worker has no HTTP port"

DEFAULT_BOOTSTRAP = "localhost:9092"
RAW_TOPIC = "weather.raw.v1"
DLQ_TOPIC = "weather.dlq.v1"


def tcp_open(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def infra_available() -> bool:
    return tcp_open("127.0.0.1", 5432) and tcp_open("127.0.0.1", 9092)


def live_database_url() -> str:
    from apps.api.core.config import settings

    return (
        f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )


def subprocess_env(**overrides: str) -> Dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + existing if existing else "")
    env.update(overrides)
    return env


def _log_dir() -> Path:
    directory = Path(os.environ.get("TMPDIR", tempfile.gettempdir())) / "bwip_test_logs"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


class ManagedProcess:
    """Subprocess wrapper that writes output to a file.

    A PIPE that is never drained blocks the child as soon as the OS pipe buffer
    fills, which silently stalls long-running workers — always use a file.
    """

    def __init__(self, args: List[str], env: Dict[str, str], cwd: Path):
        self.log_path = _log_dir() / f"{Path(args[1]).name if len(args) > 1 else 'proc'}-{uuid4().hex[:8]}.log"
        self._handle = open(self.log_path, "w", encoding="utf-8", errors="replace")
        self.args = args
        self.process = subprocess.Popen(
            args,
            cwd=str(cwd),
            env=env,
            stdout=self._handle,
            stderr=subprocess.STDOUT,
        )

    def poll(self) -> Optional[int]:
        return self.process.poll()

    def terminate(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()

    def kill(self) -> None:
        if self.process.poll() is None:
            self.process.kill()

    def wait(self, timeout: Optional[float] = None) -> int:
        return self.process.wait(timeout=timeout)

    def output(self, max_chars: int = 12000) -> str:
        try:
            self._handle.flush()
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as handle:
                return handle.read()[-max_chars:]
        except Exception:  # noqa: BLE001
            return "<unavailable>"


def start_process(args: List[str], **env_overrides: str) -> ManagedProcess:
    env = subprocess_env(**env_overrides)
    return ManagedProcess(args, env, ROOT)


def stop_process(process: Optional[ManagedProcess], timeout: float = 10.0) -> None:
    if process is None:
        return
    try:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=timeout)
    finally:
        try:
            process._handle.close()
        except Exception:  # noqa: BLE001
            pass


def wait_for_http(url: str, timeout: float = 40.0) -> httpx.Response:
    deadline = time.monotonic() + timeout
    last_error: Optional[Exception] = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(url, timeout=3.0)
            if response.status_code == 200:
                return response
        except Exception as exc:  # noqa: BLE001 - probe loop
            last_error = exc
        time.sleep(0.4)
    raise TimeoutError(f"{url} did not become ready within {timeout}s (last error: {last_error})")


def process_output(process: Optional["ManagedProcess"], max_chars: int = 12000) -> str:
    if process is None:
        return ""
    return process.output(max_chars)


# ------------------------------------------------------------------------------
# Redpanda helpers
# ------------------------------------------------------------------------------
async def publish_records(
    topic: str,
    values: Iterable[Any],
    key: Optional[str] = None,
    bootstrap_servers: str = DEFAULT_BOOTSTRAP,
) -> List[Any]:
    from aiokafka import AIOKafkaProducer

    values = list(values)
    producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None,
    )
    await producer.start()
    try:
        for value in values:
            await producer.send_and_wait(topic, value=value, key=key)
    finally:
        await producer.stop()
    return values


async def consume_matching(
    topic: str,
    predicate: Callable[[Dict[str, Any]], bool],
    timeout: float = 20.0,
    bootstrap_servers: str = DEFAULT_BOOTSTRAP,
    group_id: Optional[str] = None,
    min_matches: int = 1,
) -> List[Dict[str, Any]]:
    """Read from the real broker with a fresh consumer group and return every
    message matching ``predicate`` (proves the payload physically reached Kafka).

    Returned payloads carry ``__partition`` / ``__offset`` so callers can wait
    for the application consumer group to commit past them.
    """
    from aiokafka import AIOKafkaConsumer

    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id or f"verify-{uuid4().hex}",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    await consumer.start()
    matches: List[Dict[str, Any]] = []
    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            batch = await consumer.getmany(timeout_ms=500, max_records=200)
            for _tp, messages in batch.items():
                for message in messages:
                    try:
                        payload = json.loads(message.value.decode("utf-8"))
                    except Exception:  # noqa: BLE001
                        continue
                    if predicate(payload):
                        enriched = dict(payload)
                        enriched["__partition"] = message.partition
                        enriched["__offset"] = message.offset
                        matches.append(enriched)
            if len(matches) >= min_matches:
                break
    finally:
        await consumer.stop()
    return matches


async def wait_for_consumer_progress(
    topic: str,
    group_id: str,
    min_offsets: Dict[int, int],
    timeout: float = 25.0,
    bootstrap_servers: str = DEFAULT_BOOTSTRAP,
) -> Dict[int, int]:
    """Wait until the application consumer group has committed past the given offsets."""
    from aiokafka.admin import AIOKafkaAdminClient
    from aiokafka.structs import TopicPartition

    admin = AIOKafkaAdminClient(bootstrap_servers=bootstrap_servers)
    await admin.start()
    try:
        deadline = time.monotonic() + timeout
        committed: Dict[int, int] = {}
        while time.monotonic() < deadline:
            offsets = await admin.list_consumer_group_offsets(group_id)
            committed = {
                tp.partition: offset.offset
                for tp, offset in offsets.items()
                if tp.topic == topic
            }
            if all(committed.get(partition, -1) >= offset for partition, offset in min_offsets.items()):
                return committed
            await asyncio.sleep(0.4)
        raise TimeoutError(
            f"Consumer group {group_id} did not reach offsets {min_offsets} "
            f"(currently {committed}) within {timeout}s"
        )
    finally:
        await admin.close()


def consume_matching_sync(*args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
    return asyncio.run(consume_matching(*args, **kwargs))


def publish_records_sync(*args: Any, **kwargs: Any) -> List[Any]:
    return asyncio.run(publish_records(*args, **kwargs))


def wait_for_messages_processed(
    matches: List[Dict[str, Any]],
    topic: str = RAW_TOPIC,
    group_id: Optional[str] = None,
    timeout: float = 25.0,
) -> Dict[int, int]:
    """Block until the application consumer group has committed past ``matches``."""
    from apps.api.core.config import settings

    min_offsets: Dict[int, int] = {}
    for match in matches:
        partition = match["__partition"]
        offset = match["__offset"] + 1
        min_offsets[partition] = max(min_offsets.get(partition, -1), offset)

    return asyncio.run(
        wait_for_consumer_progress(
            topic,
            group_id or settings.KAFKA_CONSUMER_GROUP,
            min_offsets,
            timeout=timeout,
        )
    )


# ------------------------------------------------------------------------------
# PostgreSQL helpers
# ------------------------------------------------------------------------------
def live_session_factory():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(live_database_url(), pool_pre_ping=True, pool_recycle=30)
    return engine, sessionmaker(autocommit=False, autoflush=False, bind=engine)


def wait_for(predicate: Callable[[], bool], timeout: float = 25.0, interval: float = 0.4) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False
