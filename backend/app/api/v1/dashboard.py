from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_password_changed, require_roles
from app.models.user import User
from app.schemas.dashboard import DashboardOverview
from app.services.provider_factory import get_data_provider

router = APIRouter()
_dashboard_roles = ["Super Admin", "SOC Analyst", "Manager", "Auditor"]


@router.get("", response_model=DashboardOverview)
async def get_dashboard_overview(
    _: User = Depends(require_roles(_dashboard_roles)),
    __: User = Depends(require_password_changed),
    db: AsyncSession = Depends(get_db),
) -> DashboardOverview:
    provider = get_data_provider()
    return await provider.get_dashboard_overview(db)
