"""WeatherAPI.com connector runner (ticket NW-041).

Fetches current weather for the configured Indian locations, converts each
reading into the canonical observation envelope, and publishes it to the live
``weather.raw.v1`` topic so the normal consumer pipeline
(normalization -> idempotency -> clustering -> PostgreSQL/PostGIS) processes it.

Usage:
    py -m scripts.run_weather_connector                 # single poll, publish
    py -m scripts.run_weather_connector --dry-run       # fetch only, publish nothing
    py -m scripts.run_weather_connector --all           # include benign sky conditions
    py -m scripts.run_weather_connector --interval 600  # poll every 10 minutes
    py -m scripts.run_weather_connector --locations "Mumbai, India" "Delhi, India"

Exit codes: 0 = success, 1 = configuration/provider/publish failure.
"""
import argparse
import asyncio
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from apps.api.core.config import settings
from apps.api.core.logging import logger
from apps.api.schemas.reports import CanonicalReport
from services.ingestion.weatherapi import WeatherAPIConnector
from services.streaming.producer import StreamPublishError, producer


def to_envelope(report: CanonicalReport) -> Dict[str, Any]:
    """Project a canonical observation onto the ``weather.raw.v1`` envelope."""
    report_id = uuid.uuid4()
    return {
        "event_id": str(report_id),
        "source": report.source.model_dump(mode="json"),
        "observed_at": report.observed_at.isoformat(),
        "ingested_at": report.ingested_at.isoformat(),
        "content": report.content.model_dump(mode="json"),
        "location": report.location.model_dump(mode="json"),
        "classification": report.classification.model_dump(mode="json"),
        "metadata": report.metadata,
    }


async def run_once(
    connector: WeatherAPIConnector,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """One poll cycle. Publishes nothing when ``dry_run`` is set."""
    published = 0
    failures = 0

    if not dry_run:
        await producer.start()

    try:
        async for observation in connector.fetch_observations():
            if dry_run:
                published += 1
                continue
            envelope = to_envelope(observation)
            try:
                await producer.publish(
                    topic="weather.raw.v1",
                    key=envelope["event_id"],
                    payload=envelope,
                )
                published += 1
            except StreamPublishError as exc:
                failures += 1
                logger.error(f"[WeatherAPI Runner] Publish failed: {exc}")
    except RuntimeError as exc:
        logger.error(f"[WeatherAPI Runner] {exc}")
        return {
            "published": published,
            "skipped": connector.benign_skipped_total,
            "failures": failures,
            "error": str(exc),
        }
    finally:
        if not dry_run:
            await producer.stop()

    return {
        "published": published,
        "skipped": connector.benign_skipped_total,
        "failures": failures,
        "error": None,
    }


async def run_forever(
    connector: WeatherAPIConnector,
    interval_seconds: int,
    dry_run: bool,
) -> int:
    cycle = 0
    while True:
        cycle += 1
        started = datetime.now(timezone.utc)
        result = await run_once(connector, dry_run=dry_run)
        print(
            f"[cycle {cycle}] {started.isoformat(timespec='seconds')} -> "
            f"published={result['published']} benign_skipped={result['skipped']} "
            f"failures={result['failures']} error={result['error'] or '-'}",
            flush=True,
        )
        if result["error"]:
            return 1
        await asyncio.sleep(interval_seconds)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.run_weather_connector",
        description="Poll WeatherAPI.com and publish canonical observations to weather.raw.v1",
    )
    parser.add_argument("--dry-run", action="store_true", help="Fetch and report, but publish nothing")
    parser.add_argument(
        "--all",
        action="store_true",
        dest="include_benign",
        help="Also ingest benign sky conditions (Clear/Cloudy/Overcast)",
    )
    parser.add_argument("--interval", type=int, default=0, help="Seconds between polls (0 = run once)")
    parser.add_argument(
        "--locations",
        nargs="+",
        default=None,
        help="Override the configured location list for this run",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if not settings.weatherapi_configured:
        print(
            "ERROR: WEATHERAPI_API_KEY is not set.\n"
            "  1. Open .env\n"
            "  2. Set WEATHERAPI_API_KEY=<your key>\n"
            "  3. Re-run: py -m scripts.run_weather_connector",
            file=sys.stderr,
        )
        return 1

    connector = WeatherAPIConnector(
        locations=args.locations if args.locations else None,
        include_benign=args.include_benign or settings.WEATHERAPI_INCLUDE_BENIGN,
    )

    print(
        f"WeatherAPI connector | locations={len(connector.locations)} "
        f"| include_benign={connector.include_benign} "
        f"| mode={'dry-run' if args.dry_run else settings.STREAM_MODE} "
        f"| interval={args.interval}s",
        flush=True,
    )

    if args.interval > 0:
        return asyncio.run(run_forever(connector, args.interval, args.dry_run))

    result = asyncio.run(run_once(connector, dry_run=args.dry_run))
    print(
        f"published={result['published']} benign_skipped={result['skipped']} "
        f"failures={result['failures']} error={result['error'] or '-'}",
        flush=True,
    )
    return 1 if (result["error"] or result["failures"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
