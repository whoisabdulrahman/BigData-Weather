import logging
import sys
from typing import Iterable

from apps.api.core.config import settings


class SecretRedactionFilter(logging.Filter):
    """Strips configured credentials from every record before it is formatted.

    Provider SDKs (httpx, aiokafka, boto3) routinely log full request URLs, and
    WeatherAPI.com carries its credential in the query string. Without this
    filter the key would be written to stdout and any log sink.
    """

    def _secrets(self) -> Iterable[str]:
        for value in (
            settings.WEATHERAPI_API_KEY,
            settings.LOCATIONIQ_API_KEY,
            settings.MAPTILER_API_KEY,
        ):
            cleaned = (value or "").strip()
            if cleaned:
                yield cleaned

    def filter(self, record: logging.LogRecord) -> bool:
        secrets = list(self._secrets())
        if not secrets:
            return True
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - malformed record, leave untouched
            return True
        redacted = message
        for secret in secrets:
            if secret in redacted:
                redacted = redacted.replace(secret, "***REDACTED***")
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def setup_logging():
    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(SecretRedactionFilter())
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format=log_format,
        handlers=[handler],
        force=True,
    )
    # HTTP client debug logs embed the full URL (query string included).
    # Only the HTTP clients are silenced: live pipeline tests assert on
    # aiokafka INFO records, so suppressing those would break them.
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logger = logging.getLogger("bwip")
    return logger


logger = setup_logging()
