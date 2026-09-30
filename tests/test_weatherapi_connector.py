"""Unit tests for the WeatherAPI.com connector (NW-040 / NW-041).

All provider traffic is mocked — these tests never spend a quota unit and never
touch the network.
"""
import pytest

from apps.api.core.config import settings
from services.ingestion.weatherapi import WeatherAPIConnector, classify_condition


def _payload(
    lat=28.61,
    lon=77.21,
    code=1189,
    temp_c=27.4,
    wind_kph=12.6,
    precip_mm=8.2,
    name="New Delhi",
    region="Delhi",
    last_updated_epoch=1790721900,
):
    return {
        "location": {
            "name": name,
            "region": region,
            "country": "India",
            "lat": lat,
            "lon": lon,
        },
        "current": {
            "last_updated_epoch": last_updated_epoch,
            "temp_c": temp_c,
            "wind_kph": wind_kph,
            "precip_mm": precip_mm,
            "humidity": 88,
            "is_day": 1,
            "condition": {"text": "Moderate rain", "code": code},
        },
    }


def _connector(**kwargs):
    kwargs.setdefault("api_key", "test-key-not-a-real-secret")
    kwargs.setdefault("locations", ["New Delhi, India"])
    return WeatherAPIConnector(**kwargs)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------
def test_classify_maps_rain_condition_code():
    event, confidence, benign = classify_condition(1189, 27.0, 10.0)
    assert event == "RAIN"
    assert confidence > 0.5
    assert benign is False


def test_classify_maps_thunder_condition_code():
    event, _, benign = classify_condition(1276, 26.0, 30.0)
    assert event == "THUNDERSTORM"
    assert benign is False


def test_classify_marks_clear_sky_benign():
    event, _, benign = classify_condition(1000, 30.0, 8.0)
    assert benign is True
    assert event == "OTHER"


def test_classify_derives_heatwave_from_temperature():
    event, confidence, benign = classify_condition(1000, 43.5, 10.0)
    assert event == "HEATWAVE"
    assert confidence >= 0.70
    assert benign is False


def test_classify_derives_strong_wind_from_speed():
    event, confidence, benign = classify_condition(1006, 30.0, 72.0)
    assert event == "STRONG_WIND"
    assert confidence >= 0.65
    assert benign is False


def test_classify_thunderoutranks_derived_heat_signal():
    event, _, _ = classify_condition(1276, 43.0, 75.0)
    assert event == "THUNDERSTORM"


# ---------------------------------------------------------------------------
# Configuration guard
# ---------------------------------------------------------------------------
def test_connector_refuses_to_run_without_api_key():
    connector = _connector(api_key="")
    assert connector.configured is False

    async def _drain():
        return [o async for o in connector.fetch_observations()]

    with pytest.raises(RuntimeError) as excinfo:
        import asyncio

        asyncio.run(_drain())
    assert "WEATHERAPI_API_KEY" in str(excinfo.value)


def test_health_check_reports_not_configured_without_key():
    connector = _connector(api_key="")
    import asyncio

    report = asyncio.run(connector.health_check())
    assert report["status"] == "not_configured"
    assert "key" in report["detail"].lower()


# ---------------------------------------------------------------------------
# Mapping / envelope correctness
# ---------------------------------------------------------------------------
def test_observation_envelope_is_canonical_and_provenance_is_metadata():
    connector = _connector()
    observation = connector._to_observation(_payload(), "New Delhi, India")

    assert observation is not None
    assert observation.source.type.value == "weather_api"
    assert observation.source.name == "weatherapi.com"
    assert observation.location.provenance.value == "metadata"
    assert observation.location.confidence > 0.0
    assert observation.classification.event_type.value == "RAIN"
    assert observation.location.city == "New Delhi"
    assert observation.metadata["simulated"] is False


def test_observation_rejects_out_of_india_coordinates():
    connector = _connector()
    observation = connector._to_observation(
        _payload(lat=51.5, lon=-0.12), "London, United Kingdom"
    )
    assert observation is None


def test_observation_handles_malformed_payload():
    connector = _connector()
    # Missing the required nested objects entirely.
    assert connector._to_observation({"location": {}}, "x") is None
    assert connector._to_observation({}, "x") is None
    # Objects present but a required scalar is unusable.
    broken = _payload()
    broken["current"]["temp_c"] = "not-a-number"
    assert connector._to_observation(broken, "x") is None
    broken = _payload()
    del broken["location"]["lat"]
    assert connector._to_observation(broken, "x") is None


def test_provider_strings_are_length_bounded():
    connector = _connector()
    payload = _payload(name="A" * 500, region="B" * 500)
    observation = connector._to_observation(payload, "x")
    assert len(observation.location.city) <= 100
    assert len(observation.content.text) <= 1000


def test_api_key_never_appears_in_observation():
    secret = "super-secret-key-1234567890"
    connector = _connector(api_key=secret)
    observation = connector._to_observation(_payload(), "New Delhi, India")

    blob = observation.model_dump_json()
    assert secret not in blob


# ---------------------------------------------------------------------------
# Fetch loop
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fetch_skips_benign_by_default(monkeypatch):
    connector = _connector(include_benign=False)

    async def fake_get(self, client, params):
        return _payload(code=1000, temp_c=31.0)

    monkeypatch.setattr(WeatherAPIConnector, "_get", fake_get)
    results = [o async for o in connector.fetch_observations()]
    assert results == []
    assert connector.benign_skipped_total == 1


@pytest.mark.asyncio
async def test_fetch_emits_benign_when_explicitly_requested(monkeypatch):
    connector = _connector(include_benign=True)

    async def fake_get(self, client, params):
        return _payload(code=1000, temp_c=31.0)

    monkeypatch.setattr(WeatherAPIConnector, "_get", fake_get)
    results = [o async for o in connector.fetch_observations()]
    assert len(results) == 1
    assert results[0].metadata["benign"] is True


@pytest.mark.asyncio
async def test_fetch_propagates_provider_failure_instead_of_silently_succeeding(monkeypatch):
    connector = _connector()

    async def fake_get(self, client, params):
        raise ConnectionError("provider unreachable")

    monkeypatch.setattr(WeatherAPIConnector, "_get", fake_get)

    with pytest.raises(RuntimeError):
        async for _ in connector.fetch_observations():
            pass
    assert connector.error_count_total == 1


@pytest.mark.asyncio
async def test_fetch_never_leaks_api_key_into_logs(monkeypatch, caplog):
    connector = _connector(api_key="leak-me-please-098765")
    seen = {}

    async def fake_get(self, client, params):
        seen.update(params)
        return _payload()

    monkeypatch.setattr(WeatherAPIConnector, "_get", fake_get)
    with caplog.at_level("INFO"):
        async for _ in connector.fetch_observations():
            pass

    # The key is legitimately sent as a request parameter...
    assert seen["key"] == "leak-me-please-098765"
    # ...but must never reach a log record.
    assert "leak-me-please-098765" not in caplog.text


def test_locations_default_to_india():
    connector = _connector(locations=None)
    assert connector.locations == settings.WEATHERAPI_LOCATIONS
    assert len(connector.locations) >= 10


# ---------------------------------------------------------------------------
# Log redaction (the provider credential travels in the request URL)
# ---------------------------------------------------------------------------
def test_secret_redaction_filter_strips_api_key_from_log_records():
    import logging

    from apps.api.core.logging import SecretRedactionFilter

    secret = (settings.WEATHERAPI_API_KEY or "unit-test-secret-value").strip()
    assert secret, "test requires a configured WEATHERAPI_API_KEY"

    record = logging.LogRecord(
        name="bwip",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="GET https://api.weatherapi.com/v1/current.json?key=%s&q=Delhi",
        args=(secret,),
        exc_info=None,
    )

    assert SecretRedactionFilter().filter(record) is True
    rendered = record.getMessage()
    assert secret not in rendered
    assert "***REDACTED***" in rendered


def test_secret_redaction_filter_leaves_clean_records_untouched():
    import logging

    from apps.api.core.logging import SecretRedactionFilter

    record = logging.LogRecord(
        name="bwip",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="pipeline persisted observation",
        args=(),
        exc_info=None,
    )
    assert SecretRedactionFilter().filter(record) is True
    assert record.getMessage() == "pipeline persisted observation"
