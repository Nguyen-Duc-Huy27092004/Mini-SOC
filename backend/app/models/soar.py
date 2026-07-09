import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

class SoarPlaybook(Base):
    __tablename__ = "soar_playbooks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    execution_mode: Mapped[str] = mapped_column(String(50), default="Auto") # Auto, Need Approval
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    rules = relationship("SoarRule", back_populates="playbook", cascade="all, delete-orphan")
    actions = relationship("SoarAction", back_populates="playbook", cascade="all, delete-orphan", order_by="SoarAction.step_order")
    runs = relationship("SoarRun", back_populates="playbook", cascade="all, delete-orphan")

class SoarRule(Base):
    __tablename__ = "soar_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    playbook_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("soar_playbooks.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    condition_logic: Mapped[str] = mapped_column(String(50), default="AND") # AND, OR
    condition_config: Mapped[dict] = mapped_column(JSON, default=list) # JSON list of conditions
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    playbook = relationship("SoarPlaybook", back_populates="rules")

class SoarAction(Base):
    __tablename__ = "soar_actions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    playbook_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("soar_playbooks.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False) # e.g. send_email, webhook
    step_order: Mapped[int] = mapped_column(default=1)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    playbook = relationship("SoarPlaybook", back_populates="actions")

class SoarRun(Base):
    __tablename__ = "soar_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    playbook_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("soar_playbooks.id", ondelete="CASCADE"))
    trigger_source: Mapped[str] = mapped_column(String(100)) # e.g. wazuh, zabbix, manual
    trigger_data: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="Running") # Running, Success, Failed, Pending Approval
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    playbook = relationship("SoarPlaybook", back_populates="runs")
    logs = relationship("SoarLog", back_populates="run", cascade="all, delete-orphan", order_by="SoarLog.timestamp")
    approval = relationship("SoarApproval", back_populates="run", uselist=False, cascade="all, delete-orphan")

class SoarLog(Base):
    __tablename__ = "soar_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("soar_runs.id", ondelete="CASCADE"))
    action_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True) # Which action generated this log
    step_order: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(50)) # Success, Failed
    message: Mapped[str] = mapped_column(Text)
    request_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    response_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    run = relationship("SoarRun", back_populates="logs")

class SoarApproval(Base):
    __tablename__ = "soar_approvals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("soar_runs.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(50), default="Pending") # Pending, Approved, Rejected
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    run = relationship("SoarRun", back_populates="approval")
