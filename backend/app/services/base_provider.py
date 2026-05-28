from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.dashboard import DashboardOverview
from app.schemas.server import ServerSummaryResponse
from app.schemas.alert import AlertSummaryResponse, AlertQueryParams

class BaseDataProvider(ABC):
    """
    Abstract Base Class for Data Providers.
    Legacy interface; production uses WazuhDataProvider (PostgreSQL only).
    """

    @abstractmethod
    async def get_dashboard_overview(self, db: AsyncSession) -> DashboardOverview:
        """Get summarized metrics for the Executive Dashboard overview tab."""
        pass

    @abstractmethod
    async def get_servers(self, db: AsyncSession) -> ServerSummaryResponse:
        """Get systems and server health monitoring statistics."""
        pass

    @abstractmethod
    async def get_attacks(self, db: AsyncSession, mode: str = "executive") -> dict:
        """Get GeoIP and threat distribution data."""
        pass

    @abstractmethod
    async def get_endpoints(self, db: AsyncSession) -> dict:
        """Get Endpoint Security inventory and risk stats."""
        pass

    @abstractmethod
    async def get_alerts(self, db: AsyncSession, params: AlertQueryParams) -> AlertSummaryResponse:
        """Get paginated and filtered realtime alerts feed."""
        pass

    @abstractmethod
    async def get_backup_status(self, db: AsyncSession) -> dict:
        """Get snapshot and backups success/fail metrics."""
        pass

    @abstractmethod
    async def get_user_monitoring(self, db: AsyncSession) -> dict:
        """Get VPN, RDP, and user activity login statistics."""
        pass
