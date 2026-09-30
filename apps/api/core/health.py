"""Dependency readiness probes.

Every component check performs a real operation against the backing service.
No probe returns a hard-coded status: an unreachable dependency is reported as
``unavailable`` (or ``degraded`` when an intentional fallback is active).
"""
import asyncio
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import text

from apps.api.core.config import settings
from apps.api.core.logging import logger

ProbeResult = Tuple[str, Dict[str, Any]]


async def _to_thread(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


async def check_database(timeout: float = 3.0) -> ProbeResult:
    from apps.api.db.session import engine

    def probe() -> Dict[str, Any]:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            postgis_version: Optional[str] = None
            if engine.dialect.name == "postgresql":
                try:
                    postgis_version = connection.execute(
                        text("SELECT postgis_version()")
                    ).scalar()
                except Exception:  # pragma: no cover - extension guard
                    postgis_version = None
            return {
                "type": "PostgreSQL+PostGIS" if postgis_version else engine.dialect.name,
                "host": settings.POSTGRES_HOST,
                "postgis_version": postgis_version,
            }

    try:
        details = await asyncio.wait_for(_to_thread(probe), timeout=timeout)
        return "healthy", details
    except Exception as exc:
        logger.warning(f"[Readiness] Database probe failed: {exc}")
        return "unavailable", {"type": "PostgreSQL+PostGIS", "error": str(exc)}


async def check_cache(timeout: float = 3.0) -> ProbeResult:
    def probe() -> str:
        import redis

        client = redis.Redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=timeout,
            socket_timeout=timeout,
        )
        try:
            return str(client.ping())
        finally:
            client.close()

    try:
        pong = await asyncio.wait_for(_to_thread(probe), timeout=timeout + 1)
        if pong != "True":
            return "degraded", {"type": "Redis", "url": settings.REDIS_URL, "response": pong}
        return "healthy", {"type": "Redis", "url": settings.REDIS_URL}
    except Exception as exc:
        logger.warning(f"[Readiness] Redis probe failed: {exc}")
        return "unavailable", {"type": "Redis", "url": settings.REDIS_URL, "error": str(exc)}


async def check_streaming(timeout: float = 5.0) -> ProbeResult:
    if settings.STREAM_MODE != "redpanda":
        return "degraded", {
            "type": "InMemoryStreamBus",
            "mode": settings.STREAM_MODE,
            "broker": settings.KAFKA_BOOTSTRAP_SERVERS,
            "detail": "Demo/test transport active — live Redpanda broker is not in use.",
        }

    required = [t.strip() for t in settings.KAFKA_TOPIC_BOOTSTRAP.split(",") if t.strip()]

    async def probe() -> Dict[str, Any]:
        from aiokafka.admin import AIOKafkaAdminClient

        admin = AIOKafkaAdminClient(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            client_id=f"{settings.KAFKA_CLIENT_ID}-readiness",
        )
        await admin.start()
        try:
            topics = sorted(await admin.list_topics())
        finally:
            await admin.close()
        return {"topics": topics}

    try:
        result = await asyncio.wait_for(probe(), timeout=timeout)
        missing = [t for t in required if t not in result["topics"]]
        if missing:
            return "degraded", {
                "type": "Redpanda",
                "bootstrap": settings.KAFKA_BOOTSTRAP_SERVERS,
                "missing_topics": missing,
            }
        return "healthy", {
            "type": "Redpanda",
            "bootstrap": settings.KAFKA_BOOTSTRAP_SERVERS,
            "topics": required,
        }
    except Exception as exc:
        logger.warning(f"[Readiness] Redpanda probe failed: {exc}")
        return "unavailable", {
            "type": "Redpanda",
            "bootstrap": settings.KAFKA_BOOTSTRAP_SERVERS,
            "error": str(exc),
        }


async def check_object_store(timeout: float = 4.0) -> ProbeResult:
    def probe() -> Dict[str, Any]:
        import boto3
        from botocore.client import Config
        from botocore.exceptions import ClientError

        client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=Config(signature_version="s3v4", retries={"max_attempts": 1}),
        )
        buckets = [settings.S3_BUCKET_MEDIA, settings.S3_BUCKET_RAW]
        missing = []
        for bucket in buckets:
            try:
                client.head_bucket(Bucket=bucket)
            except ClientError as exc:
                code = str(exc.response.get("Error", {}).get("Code", ""))
                if code in ("404", "NoSuchBucket", "NotFound"):
                    missing.append(bucket)
                else:
                    raise
        return {"endpoint": settings.S3_ENDPOINT, "buckets": buckets, "missing_buckets": missing}

    try:
        details = await asyncio.wait_for(_to_thread(probe), timeout=timeout)
        if details["missing_buckets"]:
            return "degraded", details
        return "healthy", details
    except Exception as exc:
        logger.warning(f"[Readiness] Object store probe failed: {exc}")
        return "unavailable", {"endpoint": settings.S3_ENDPOINT, "error": str(exc)}


def ensure_object_store_buckets(timeout: float = 4.0) -> Dict[str, Any]:
    """Idempotent bucket bootstrap for the configured S3-compatible store.

    Never raises: a missing/unreachable object store is reported in the result so
    callers can log it without taking the API process down.
    """
    import boto3
    from botocore.client import Config
    from botocore.exceptions import ClientError

    client = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=Config(
            signature_version="s3v4",
            retries={"max_attempts": 1},
            connect_timeout=timeout,
            read_timeout=timeout,
        ),
    )
    buckets = [settings.S3_BUCKET_MEDIA, settings.S3_BUCKET_RAW]
    created: list = []
    existing: list = []
    failures: Dict[str, str] = {}
    for bucket in buckets:
        try:
            client.head_bucket(Bucket=bucket)
            existing.append(bucket)
            continue
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code not in ("404", "NoSuchBucket", "NotFound"):
                failures[bucket] = str(exc)
                continue
        except Exception as exc:  # connectivity/credentials problem
            failures[bucket] = str(exc)
            continue
        try:
            client.create_bucket(Bucket=bucket)
            created.append(bucket)
        except Exception as exc:
            failures[bucket] = str(exc)
    return {"endpoint": settings.S3_ENDPOINT, "created": created, "existing": existing, "failures": failures}
