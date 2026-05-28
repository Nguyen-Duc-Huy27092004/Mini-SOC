from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    Index,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# ============================================================
# Enums
# ============================================================

class AssetCriticality(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AssetStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    RETIRED = "retired"
    QUARANTINED = "quarantined"


class AssetType(str, enum.Enum):
    SERVER = "server"
    WORKSTATION = "workstation"
    LAPTOP = "laptop"
    VM = "virtual_machine"
    FIREWALL = "firewall"
    SWITCH = "switch"
    ROUTER = "router"
    CLOUD = "cloud"
    OTHER = "other"


# ============================================================
# Asset Model
# ============================================================

class Asset(Base):

    __tablename__ = "assets"

    __table_args__ = (

        Index(
            "idx_assets_hostname",
            "hostname",
        ),

        Index(
            "idx_assets_agent_id",
            "agent_id",
        ),

        Index(
            "idx_assets_ip",
            "ip_address",
        ),

        Index(
            "idx_assets_status_last_seen",
            "status",
            "last_seen",
        ),

        CheckConstraint(
            "risk_score >= 0 AND risk_score <= 100",
            name="chk_asset_risk_score",
        ),
    )

    # ========================================================
    # Identity
    # ========================================================

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    agent_id: Mapped[str | None] = mapped_column(
        String(50),
        unique=True,
        nullable=True,
    )

    hostname: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    ip_address: Mapped[str] = mapped_column(
        INET,
        nullable=False,
    )

    mac_address: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    fqdn: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    domain: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # ========================================================
    # Asset Metadata
    # ========================================================

    asset_type: Mapped[AssetType] = mapped_column(
        Enum(AssetType),
        default=AssetType.SERVER,
        nullable=False,
    )

    os_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    os_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    department: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    owner: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    location: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # ========================================================
    # Security Metadata
    # ========================================================

    criticality: Mapped[AssetCriticality] = mapped_column(
        Enum(AssetCriticality),
        default=AssetCriticality.MEDIUM,
        nullable=False,
    )

    status: Mapped[AssetStatus] = mapped_column(
        Enum(AssetStatus),
        default=AssetStatus.ACTIVE,
        nullable=False,
    )

    risk_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    # ========================================================
    # Inventory / Source Tracking
    # ========================================================

    source: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="wazuh/manual/api/import",
    )

    last_seen: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ========================================================
    # Audit
    # ========================================================

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ========================================================
    # Helpers
    # ========================================================

    @property
    def is_online(self) -> bool:

        if not self.last_seen:
            return False

        delta = (
            datetime.now(timezone.utc)
            - self.last_seen
        )

        return delta.total_seconds() < 300

    def __repr__(self) -> str:

        return (
            f"<Asset "
            f"hostname={self.hostname} "
            f"ip={self.ip_address}>"
        )