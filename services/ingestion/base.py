from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any, Optional
from datetime import datetime, timezone
from apps.api.schemas.reports import CanonicalReport


class BaseConnector(ABC):
    """
    Abstract Base Class for all external and citizen data source connectors.
    Enforces canonical output envelope, health reporting, and cursor tracking.
    """

    def __init__(self, source_name: str, source_type: str):
        self.source_name = source_name
        self.source_type = source_type
        self.last_sync_time: Optional[datetime] = None
        self.records_ingested_total: int = 0
        self.error_count_total: int = 0

    @abstractmethod
    async def fetch_observations(self) -> AsyncGenerator[CanonicalReport, None]:
        """
        Polls or listens to external source and yields CanonicalReport objects.
        Must handle its own retries and wrap source errors.
        """
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Returns connection and latency status for the source.
        """
        pass

    def record_success(self, count: int = 1):
        self.records_ingested_total += count
        self.last_sync_time = datetime.now(timezone.utc)

    def record_error(self):
        self.error_count_total += 1
