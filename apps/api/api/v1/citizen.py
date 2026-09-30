import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, status, HTTPException
from apps.api.schemas.reports import CitizenReportCreate, CitizenReportResponse
from apps.api.core.logging import logger
from services.streaming.producer import producer, StreamPublishError

router = APIRouter(prefix="/citizen", tags=["Citizen Reporting"])


@router.post(
    "/reports",
    response_model=CitizenReportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a citizen weather observation report",
    description=(
        "Accepts crowdsourced weather observation reports, performs schema and India bounding-box validation, "
        "constructs the canonical observation envelope, and publishes asynchronously to the streaming topic (weather.raw.v1)."
    ),
)
async def submit_citizen_report(payload: CitizenReportCreate) -> CitizenReportResponse:
    report_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    reference_number = f"BWIP-{now.strftime('%Y%m%d')}-{str(report_id)[:8].upper()}"

    # 1. State: VALIDATED (passed Pydantic schema & bounding box validation)
    # 2. State: ACCEPTED (assigned UUID and tracking reference)
    # 3. Construct canonical observation envelope
    canonical_envelope = {
        "event_id": str(report_id),
        "source": {
            "type": "citizen",
            "name": "citizen_portal",
            "external_id": reference_number,
        },
        "observed_at": (payload.observed_at or now).isoformat(),
        "ingested_at": now.isoformat(),
        "content": {
            "text": payload.text,
            "language": "en",
            "media": payload.media_urls,
        },
        "location": {
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "city": payload.city,
            "district": payload.district,
            "state": payload.state,
            "provenance": payload.location_provenance.value,
            "confidence": 0.85 if payload.location_provenance.value == "gps" else 0.60,
        },
        "classification": {
            "event_type": payload.event_type.value,
            "confidence": 0.70,
        },
        "metadata": {
            "client_reference": reference_number,
        },
    }

    # 4. State: PUBLISHED (to streaming topic weather.raw.v1)
    # An unavailable stream is a hard failure — never reported as a success.
    try:
        envelope = await producer.publish(
            topic="weather.raw.v1",
            key=str(report_id),
            payload=canonical_envelope,
        )
    except StreamPublishError as exc:
        logger.error(f"[CitizenAPI] Report {report_id} rejected: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Ingestion stream unavailable. The observation was NOT accepted. "
                "Retry once the streaming backend recovers."
            ),
        ) from exc

    logger.info(
        f"[CitizenAPI] Report {report_id} accepted & published to weather.raw.v1 "
        f"(Ref: {reference_number}, transport: {envelope['transport']})"
    )

    return CitizenReportResponse(
        id=report_id,
        reference_number=reference_number,
        status="ACCEPTED",
        processing_status="ACCEPTED",
        stream_topic="weather.raw.v1",
        transport=envelope["transport"],
        lifecycle=["VALIDATED", "ACCEPTED", "PUBLISHED"],
        message="Observation report validated, accepted, and published to ingestion stream.",
        received_at=now,
    )
