from typing import List, Union
import json
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # General Platform
    PROJECT_NAME: str = "National Weather Big Data Analytics Platform"
    PROJECT_SLUG: str = "bwip"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "change-this-to-a-secure-random-secret-key-at-least-32-chars-long"

    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000"
    ]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Database (PostgreSQL + PostGIS)
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "weather_platform"
    POSTGRES_USER: str = "weather_user"
    POSTGRES_PASSWORD: str = "weather_secure_dev_password"
    DATABASE_URL: str = "postgresql://weather_user:weather_secure_dev_password@localhost:5432/weather_platform"

    # Streaming (Redpanda / Kafka)
    # STREAM_MODE:
    #   "redpanda" -> live broker is mandatory; publish failures surface as errors (no silent fallback)
    #   "bus"      -> deterministic in-memory bus for unit tests and demo/replay (DEC-002)
    STREAM_MODE: str = "redpanda"
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_CLIENT_ID: str = "bwip-api"
    KAFKA_CONSUMER_GROUP: str = "bwip-observation-pipeline"
    KAFKA_AUTO_OFFSET_RESET: str = "earliest"
    KAFKA_TOPIC_RAW: str = "weather.raw.v1"
    KAFKA_TOPIC_NORMALIZED: str = "weather.normalized.v1"
    KAFKA_TOPIC_CLASSIFIED: str = "weather.classified.v1"
    KAFKA_TOPIC_GEOLOCATED: str = "weather.geolocated.v1"
    KAFKA_TOPIC_DEDUPED: str = "weather.deduped.v1"
    KAFKA_TOPIC_VERIFIED: str = "weather.verified.v1"
    KAFKA_TOPIC_INCIDENTS: str = "weather.incidents.v1"
    KAFKA_TOPIC_ALERTS: str = "weather.alerts.v1"
    KAFKA_TOPIC_DLQ: str = "weather.dlq.v1"
    KAFKA_TOPIC_BOOTSTRAP: str = "weather.raw.v1,weather.dlq.v1"

    # Cache (Redis)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_URL: str = "redis://localhost:6379/0"

    # Object Storage (MinIO / S3)
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_MEDIA: str = "weather-media"
    S3_BUCKET_RAW: str = "weather-raw-payloads"
    S3_REGION: str = "us-east-1"

    # External Data Providers (NW-041 Weather API connector)
    # Secrets are supplied via .env only — never hard-code credentials here.
    WEATHERAPI_API_KEY: str = ""
    WEATHERAPI_BASE_URL: str = "https://api.weatherapi.com/v1"
    WEATHERAPI_ENABLED: bool = False
    WEATHERAPI_TIMEOUT_SECONDS: float = 10.0
    WEATHERAPI_INCLUDE_BENIGN: bool = False
    WEATHERAPI_LOCATIONS: List[str] = [
        "New Delhi, India",
        "Mumbai, India",
        "Chennai, India",
        "Kolkata, India",
        "Bengaluru, India",
        "Hyderabad, India",
        "Ahmedabad, India",
        "Pune, India",
        "Jaipur, India",
        "Lucknow, India",
        "Guwahati, India",
        "Bhubaneswar, India",
        "Kochi, India",
        "Chandigarh, India",
        "Patna, India",
    ]

    @field_validator("WEATHERAPI_LOCATIONS", mode="before")
    @classmethod
    def assemble_weather_locations(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.strip().startswith("["):
                return [i.strip() for i in json.loads(v) if i.strip()]
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @property
    def weatherapi_configured(self) -> bool:
        return bool(self.WEATHERAPI_API_KEY.strip())

    # Geocoding provider (LocationIQ) — reverse/forward geocoding for reports
    # and location provenance (provenance = "geocoded" when used).
    LOCATIONIQ_API_KEY: str = ""
    LOCATIONIQ_BASE_URL: str = "https://us1.locationiq.com/v1"
    LOCATIONIQ_TIMEOUT_SECONDS: float = 8.0
    LOCATIONIQ_EMAIL: str = ""

    # Map rendering provider (MapTiler) — consumed by the Next.js frontend
    # for vector tiles, sprites and glyphs. Restricted to the local origin.
    MAPTILER_API_KEY: str = ""
    MAPTILER_STYLE_URL: str = "https://api.maptiler.com/maps/streets-v2/style.json"

    @property
    def locationiq_configured(self) -> bool:
        return bool(self.LOCATIONIQ_API_KEY.strip())

    @property
    def maptiler_configured(self) -> bool:
        return bool(self.MAPTILER_API_KEY.strip())


settings = Settings()
