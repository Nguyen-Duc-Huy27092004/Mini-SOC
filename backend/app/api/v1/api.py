from fastapi import APIRouter

from app.api.v1.alerts import router as alerts_router
from app.api.v1.attacks import router as attacks_router
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.backup import router as backup_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.endpoints import router as endpoints_router
from app.api.v1.health import router as health_router
from app.api.v1.incidents import router as incidents_router
from app.api.v1.monitoring import router as monitoring_router
from app.api.v1.servers import router as servers_router
from app.api.v1.soc_dashboard import router as soc_dashboard_router
from app.api.v1.users import router as users_router

api_router = APIRouter()

api_router.include_router(health_router, prefix="/health", tags=["Health"])
api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
api_router.include_router(soc_dashboard_router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(dashboard_router, prefix="/dashboard/overview", tags=["Dashboard Overview"])
api_router.include_router(alerts_router, prefix="/alerts", tags=["Alerts"])
api_router.include_router(incidents_router, prefix="/incidents", tags=["Incidents"])
api_router.include_router(servers_router, prefix="/servers", tags=["Servers"])
api_router.include_router(attacks_router, prefix="/attacks", tags=["Attacks"])
api_router.include_router(endpoints_router, prefix="/endpoints", tags=["Endpoints"])
api_router.include_router(backup_router, prefix="/backup", tags=["Backup"])
api_router.include_router(users_router, prefix="/users", tags=["Users"])
api_router.include_router(audit_router, prefix="/audit", tags=["Audit"])
api_router.include_router(monitoring_router, prefix="/monitoring", tags=["Monitoring"])
