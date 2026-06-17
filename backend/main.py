from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.metrics import setup_metrics
from app.core.redis_client import close_redis
from app.middleware.correlation import CorrelationIdMiddleware
from app.collector import start_collector
from app.websocket.manager import manager
from app.websocket.routes import router as ws_router

logger = structlog.get_logger()

collector_task: asyncio.Task | None = None
sync_agents_task: asyncio.Task | None = None
sync_zabbix_task: asyncio.Task | None = None


def _init_sentry() -> None:
    if settings.ENABLE_SENTRY and settings.SENTRY_DSN:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(dsn=settings.SENTRY_DSN, integrations=[FastApiIntegration()])


async def _sync_agents_loop() -> None:
    """
    Periodically sync agents from Wazuh API to database.
    Runs every 5 minutes to keep EndpointInventory table updated.
    """
    from app.collector import get_collector
    
    collector = get_collector()
    
    while True:
        try:
            count = await asyncio.wait_for(
                collector.sync_endpoint_inventory(),
                timeout=30.0,
            )
            
            await logger.ainfo(
                "agents_synced",
                count=count,
            )
        
        except asyncio.TimeoutError:
            await logger.awarning(
                "agents_sync_timeout",
            )
        
        except Exception:
            await logger.aerror(
                "agents_sync_failed",
                exc_info=True,
            )
        
        # Wait 5 minutes before next sync
        await asyncio.sleep(300)


async def _sync_zabbix_loop() -> None:
    """
    Periodically sync Zabbix snapshot data to Postgres.
    Runs every 60 seconds.
    """
    from app.core.database import async_session_maker
    from app.services.zabbix.zabbix_service import zabbix_service
    
    # Check if Zabbix is enabled
    if getattr(settings, "ZABBIX_ENABLED", False) is False:
        await logger.ainfo("zabbix_sync_disabled")
        return
        
    while True:
        try:
            async with async_session_maker() as db:
                await zabbix_service.sync_to_db(db)
        except Exception:
            await logger.aerror("zabbix_sync_loop_failed", exc_info=True)
        
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    _init_sentry()
    await logger.ainfo("app_starting", env=settings.ENV, version="2.0.0")

    # Start WebSocket subscription listener
    manager.start_listener_task()
    
    # Start real-time alert collector
    global collector_task
    collector_task = asyncio.create_task(start_collector())
    
    # Start periodic agent sync from Wazuh API
    global sync_agents_task
    sync_agents_task = asyncio.create_task(_sync_agents_loop())

    # Start periodic Zabbix sync
    global sync_zabbix_task
    sync_zabbix_task = asyncio.create_task(_sync_zabbix_loop())

    yield

    await logger.ainfo("app_shutting_down")
    manager.stop_listener_task()
    
    if collector_task:
        collector_task.cancel()
        try:
            await asyncio.wait_for(asyncio.gather(collector_task, return_exceptions=True), timeout=5.0)
        except asyncio.TimeoutError:
            pass
    
    if sync_agents_task:
        sync_agents_task.cancel()
        try:
            await asyncio.wait_for(asyncio.gather(sync_agents_task, return_exceptions=True), timeout=5.0)
        except asyncio.TimeoutError:
            pass
            
    if sync_zabbix_task:
        sync_zabbix_task.cancel()
        try:
            await asyncio.wait_for(asyncio.gather(sync_zabbix_task, return_exceptions=True), timeout=5.0)
        except asyncio.TimeoutError:
            pass
    
    await close_redis()
    await logger.ainfo("app_stopped")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Enterprise Mini SOC Portal - Real-Time Wazuh Integration",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.DEBUG else None,
)

app.add_middleware(CorrelationIdMiddleware)

# Security headers middleware
from app.middleware.security_headers import SecurityHeadersMiddleware
app.add_middleware(SecurityHeadersMiddleware)

if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(o).rstrip("/") for o in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Request-ID"],
    )

register_exception_handlers(app)
setup_metrics(app)
app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(ws_router)
