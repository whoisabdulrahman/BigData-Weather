"""WeatherAPI.com current-weather connector (tickets NW-040 / NW-041).

Implements the :class:`BaseConnector` contract and emits the canonical
observation envelope consumed by ``weather.raw.v1``.

Security / correctness notes:
* The provider credential is read from ``settings.WEATHERAPI_API_KEY`` (.env) and
  is never logged, never returned from an API, and never persisted to the database.
* Provider responses are treated as untrusted input: only whitelisted, scalar,
  length-bounded fields are copied into the observation envelope.
* Location provenance is ``metadata`` (provider-supplied coordinates), never
  ``gps`` — an external weather point is not citizen GPS evidence.
* Model/provider output never decides verification status; it only produces a
  probabilistic classification confidence.
"""
import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from apps.api.core.config import settings
from apps.api.core.logging import logger
from apps.api.schemas.reports import CanonicalReport
from services.ingestion.base import BaseConnector

# ---------------------------------------------------------------------------
# WeatherAPI.com condition code -> platform taxonomy
# Documentation: https://www.weatherapi.com/docs/weather_conditions.json
# ---------------------------------------------------------------------------
_CONDITION_CODE_TO_EVENT: Dict[int, str] = {
    # Rain / drizzle
    1063: "RAIN", 1150: "RAIN", 1153: "RAIN", 1156: "RAIN", 1159: "RAIN",
    1162: "RAIN", 1171: "RAIN", 1173: "RAIN", 1177: "RAIN", 1180: "RAIN",
    1183: "RAIN", 1186: "RAIN", 1189: "RAIN", 1192: "RAIN", 1195: "RAIN",
    1197: "RAIN", 1199: "RAIN", 1201: "RAIN", 1240: "RAIN", 1243: "RAIN",
    1246: "RAIN",
    # Thunder
    1087: "THUNDERSTORM", 1273: "THUNDERSTORM", 1276: "THUNDERSTORM",
    # Fog / mist
    1030: "FOG", 1135: "FOG", 1147: "FOG",
    # Ice pellets / hail-like
    1237: "HAILSTORM", 1261: "HAILSTORM", 1264: "HAILSTORM",
    # Snow / sleet -> no dedicated MVP class, keep as OTHER (still notable)
    1066: "OTHER", 1069: "OTHER", 1114: "OTHER", 1117: "OTHER",
    1204: "OTHER", 1207: "OTHER", 1210: "OTHER", 1213: "OTHER",
    1216: "OTHER", 1219: "OTHER", 1222: "OTHER", 1225: "OTHER",
    1227: "OTHER", 1249: "OTHER", 1252: "OTHER", 1255: "OTHER",
    1258: "OTHER", 1279: "OTHER", 1282: "OTHER",
}

# Benign sky conditions: ingested only when --include-benign / ENABLED flag asks
# for a full grid snapshot, so the incident table is not flooded with "Clear".
_BENIGN_CONDITION_CODES = {1000, 1003, 1006, 1009}

_EVENT_RANK = {
    "THUNDERSTORM": 7,
    "HAILSTORM": 6,
    "CYCLONE": 6,
    "FLOOD": 6,
    "RAIN": 5,
    "LANDSLIDE": 5,
    "HEATWAVE": 4,
    "STRONG_WIND": 3,
    "DUST_STORM": 3,
    "FOG": 2,
    "OTHER": 1,
}

_HEATWAVE_THRESHOLD_C = 40.0
_STRONG_WIND_THRESHOLD_KPH = 40.0


def classify_condition(
    condition_code: int,
    temp_c: float,
    wind_kph: float,
) -> tuple[str, float, bool]:
    """Map a provider condition into the platform taxonomy.

    Returns ``(event_type, confidence, is_benign)``.
    Confidence reflects how directly the provider signal supports the class;
    it is a probabilistic score, never a truth label.
    """
    candidates: List[tuple[str, float]] = []

    mapped = _CONDITION_CODE_TO_EVENT.get(int(condition_code))
    if mapped:
        base_confidence = 0.88 if mapped != "OTHER" else 0.45
        candidates.append((mapped, base_confidence))

    if float(temp_c) >= _HEATWAVE_THRESHOLD_C:
        # Confidence grows with how far the reading is past the threshold.
        over = min(float(temp_c) - _HEATWAVE_THRESHOLD_C, 10.0)
        candidates.append(("HEATWAVE", round(0.70 + (over / 10.0) * 0.25, 2)))

    if float(wind_kph) >= _STRONG_WIND_THRESHOLD_KPH:
        over = min(float(wind_kph) - _STRONG_WIND_THRESHOLD_KPH, 60.0)
        candidates.append(("STRONG_WIND", round(0.65 + (over / 60.0) * 0.30, 2)))

    if not candidates:
        return "OTHER", 0.30, True

    # A direct condition-code match wins over a derived threshold signal.
    candidates.sort(key=lambda c: (_EVENT_RANK.get(c[0], 0), c[1]), reverse=True)
    event_type, confidence = candidates[0]

    is_benign = int(condition_code) in _BENIGN_CONDITION_CODES and event_type == "OTHER"
    return event_type, min(round(confidence, 2), 0.99), is_benign


def _safe_text(value: Any, limit: int = 200) -> str:
    """Coerce untrusted provider strings to a bounded, single-line value."""
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


class WeatherAPIConnector(BaseConnector):
    """Polls WeatherAPI.com ``current.json`` for configured Indian locations."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        locations: Optional[List[str]] = None,
        include_benign: bool = False,
        timeout_seconds: Optional[float] = None,
    ):
        super().__init__(source_name="weatherapi.com", source_type="weather_api")
        self.api_key = (api_key if api_key is not None else settings.WEATHERAPI_API_KEY).strip()
        self.base_url = (base_url or settings.WEATHERAPI_BASE_URL).rstrip("/")
        self.locations = list(locations if locations is not None else settings.WEATHERAPI_LOCATIONS)
        self.include_benign = include_benign
        self.timeout_seconds = timeout_seconds or settings.WEATHERAPI_TIMEOUT_SECONDS
        self.benign_skipped_total = 0

    # -- configuration ----------------------------------------------------
    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _request_url(self) -> str:
        return f"{self.base_url}/current.json"

    async def _get(self, client: httpx.AsyncClient, params: Dict[str, str]) -> Dict[str, Any]:
        response = await client.get(self._request_url(), params=params)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise ValueError("WeatherAPI returned a non-object JSON body")
        return body

    # -- contract ---------------------------------------------------------
    async def fetch_observations(self) -> AsyncGenerator[CanonicalReport, None]:
        """Yield one canonical observation per configured location.

        Provider failures are recorded and re-raised as ``RuntimeError`` so a
        broken key or unreachable endpoint never silently produces "no data".
        """
        if not self.configured:
            raise RuntimeError(
                "WeatherAPI connector is not configured: WEATHERAPI_API_KEY is empty. "
                "Add it to .env (see .env.example)."
            )
        if not self.locations:
            raise RuntimeError("WeatherAPI connector has no configured locations.")

        headers = {"Accept": "application/json"}
        timeout = httpx.Timeout(self.timeout_seconds)
        emitted = 0

        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            for location in self.locations:
                try:
                    body = await self._get(client, {"key": self.api_key, "q": location, "aqi": "no"})
                except Exception as exc:  # noqa: BLE001 - provider errors are wrapped
                    self.record_error()
                    self.last_error = f"{location}: {type(exc).__name__}: {exc}"
                    logger.error(f"[WeatherAPI] fetch failed for '{location}': {type(exc).__name__}: {exc}")
                    raise RuntimeError(
                        f"WeatherAPI connector failed while fetching '{location}'. "
                        "The observation batch is incomplete and was not reported as a success."
                    ) from exc

                observation = self._to_observation(body, location)
                if observation is None:
                    continue
                if observation.metadata.get("benign") and not self.include_benign:
                    self.benign_skipped_total += 1
                    continue

                emitted += 1
                yield observation

        self.record_success(emitted)
        logger.info(
            f"[WeatherAPI] Emitted {emitted}/{len(self.locations)} observations "
            f"(include_benign={self.include_benign})"
        )

    async def health_check(self) -> Dict[str, Any]:
        """Single round-trip probe. Never logs or returns the API key."""
        if not self.configured:
            return {
                "source": self.source_name,
                "status": "not_configured",
                "enabled": settings.WEATHERAPI_ENABLED,
                "detail": "WEATHERAPI_API_KEY is not set in .env",
                "locations_configured": len(self.locations),
            }
        if not self.locations:
            return {
                "source": self.source_name,
                "status": "not_configured",
                "enabled": settings.WEATHERAPI_ENABLED,
                "detail": "No locations configured",
            }

        started = asyncio.get_event_loop().time()
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds)) as client:
                await self._get(
                    client,
                    {"key": self.api_key, "q": self.locations[0], "aqi": "no"},
                )
            latency_ms = round((asyncio.get_event_loop().time() - started) * 1000, 1)
            return {
                "source": self.source_name,
                "status": "healthy",
                "enabled": settings.WEATHERAPI_ENABLED,
                "latency_ms": latency_ms,
                "locations_configured": len(self.locations),
                "records_ingested_total": self.records_ingested_total,
                "error_count_total": self.error_count_total,
                "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
            }
        except Exception as exc:  # noqa: BLE001 - surfaced as unhealthy status
            return {
                "source": self.source_name,
                "status": "unhealthy",
                "enabled": settings.WEATHERAPI_ENABLED,
                "detail": f"{type(exc).__name__}: {exc}",
                "locations_configured": len(self.locations),
                "error_count_total": self.error_count_total,
            }

    # -- mapping ----------------------------------------------------------
    def _to_observation(self, body: Dict[str, Any], queried_location: str) -> Optional[CanonicalReport]:
        """Convert a provider payload into the canonical observation envelope.

        Returns ``None`` when the payload lacks the fields needed to build a
        trustworthy observation (malformed / partial provider response).
        """
        location = body.get("location")
        current = body.get("current")
        if not isinstance(location, dict) or not isinstance(current, dict):
            logger.warning(f"[WeatherAPI] Malformed response for '{queried_location}' (missing location/current)")
            return None

        condition = current.get("condition")
        condition = condition if isinstance(condition, dict) else {}
        condition_code = int(condition.get("code", -1))

        try:
            latitude = float(location["lat"])
            longitude = float(location["lon"])
            temp_c = float(current.get("temp_c", 0.0))
            wind_kph = float(current.get("wind_kph", 0.0))
            precip_mm = float(current.get("precip_mm", 0.0))
            humidity = int(current.get("humidity", 0))
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning(f"[WeatherAPI] Malformed payload for '{queried_location}': {exc}")
            return None

        # India bounding box — a provider payload outside India is rejected.
        if not (6.0 <= latitude <= 38.0 and 68.0 <= longitude <= 98.0):
            logger.warning(
                f"[WeatherAPI] Rejected out-of-bounds coordinate "
                f"({latitude}, {longitude}) for '{queried_location}'"
            )
            return None

        event_type, confidence, is_benign = classify_condition(condition_code, temp_c, wind_kph)
        condition_text = _safe_text(condition.get("text"), 80) or "Unknown"
        city = _safe_text(location.get("name"), 100) or queried_location
        region = _safe_text(location.get("region"), 100)

        last_updated_epoch = current.get("last_updated_epoch")
        try:
            observed_at = datetime.fromtimestamp(int(last_updated_epoch), tz=timezone.utc)
        except (TypeError, ValueError):
            observed_at = datetime.now(timezone.utc)

        text = (
            f"{condition_text} in {city}"
            + (f", {region}" if region else "")
            + f" — {temp_c:.1f}°C, wind {wind_kph:.0f} km/h, "
            + f"precipitation {precip_mm:.1f} mm, humidity {humidity}%."
        )

        return CanonicalReport(
            source={
                "type": "weather_api",
                "name": self.source_name,
                "external_id": f"{self.source_name}:{city}:{int(last_updated_epoch or 0)}",
            },
            observed_at=observed_at,
            content={
                "text": text[:1000],
                "language": "en",
                "media": [],
            },
            location={
                "latitude": latitude,
                "longitude": longitude,
                "city": city,
                "district": None,
                "state": region or None,
                "provenance": "metadata",
                "confidence": 0.85,
            },
            classification={
                "event_type": event_type,
                "confidence": confidence,
            },
            metadata={
                "provider": "weatherapi.com",
                "condition_code": condition_code,
                "condition_text": condition_text,
                "temp_c": temp_c,
                "wind_kph": wind_kph,
                "precip_mm": precip_mm,
                "humidity": humidity,
                "is_day": bool(current.get("is_day", 1)),
                "benign": is_benign,
                "queried_location": queried_location,
                "simulated": False,
            },
        )
