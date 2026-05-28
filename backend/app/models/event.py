"""Wazuh Alert Event Models - Real-time event storage and querying."""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class WazuhEvent(Base):
    """
    Normalized Wazuh Alert Event.
    
    Stores normalized, deduplicated alerts from Wazuh Manager's alerts.json.
    Single source of truth for all SOC event data.
    """
    __tablename__ = "wazuh_events"
    __table_args__ = (
        Index("idx_event_timestamp", "event_timestamp", postgresql_using="brin"),
        Index("idx_event_agent_id", "agent_id"),
        Index("idx_event_severity", "severity"),
        Index("idx_event_suppressed", "is_suppressed"),
        Index("idx_event_rule_id", "rule_id"),
        Index("idx_event_source_ip", "source_ip"),
        Index("idx_event_dest_ip", "dest_ip"),
        Index("idx_event_created", "created_at"),
    )

    # Unique Event Identifier
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True, unique=True)  # Wazuh event ID
    
    # Timestamp (BRIN indexed for time-series)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    
    # Agent Information
    agent_id: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(255), nullable=False)
    manager: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Source & Destination (Network Forensics)
    source_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True, index=True)
    source_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_user: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    
    dest_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True, index=True)
    dest_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    dest_user: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Severity & Classification
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # critical, high, medium, low
    rule_id: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    rule_description: Mapped[str] = mapped_column(Text, nullable=False)
    rule_group: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_level: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Alert Message & Details
    message: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # file_integrity_control, authentication, malware, etc.
    
    # GeoIP Information (enrichment)
    source_country: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    source_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    dest_country: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    
    # Risk & Suppression
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_suppressed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    
    # Raw Wazuh data (for debugging/advanced queries)
    wazuh_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    suppressions = relationship("AlertSuppression", back_populates="event", cascade="all, delete-orphan")
    risk_record = relationship("EventRisk", back_populates="event", uselist=False, cascade="all, delete-orphan")


class AlertSuppression(Base):
    """
    Alert Suppression & Deduplication State.
    
    Tracks suppression windows and grouping for duplicate/burst alerts.
    Prevents alert spam and enables intelligent grouping.
    """
    __tablename__ = "alert_suppressions"
    __table_args__ = (
        Index("idx_suppression_agent_rule", "agent_id", "rule_id"),
        Index("idx_suppression_expires", "suppression_expires_at"),
        Index("idx_suppression_status", "status"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("wazuh_events.id", ondelete="CASCADE"), nullable=False)
    
    # Suppression Type
    suppression_type: Mapped[str] = mapped_column(
        String(50), 
        nullable=False,
        # Types: deduplication, time_window, burst_grouping, repeated_attack
    )
    
    # Grouping Key (for burst/repeated attack grouping)
    group_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    # Affected alerts in this group
    agent_id: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    rule_id: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    source_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    dest_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    
    # Suppression Window
    suppression_starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    suppression_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    
    # Counts
    alert_count: Mapped[int] = mapped_column(Integer, default=1)
    display_alert_count: Mapped[int] = mapped_column(Integer, default=1)  # How many to show user
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)  # active, expired, resolved, acknowledged
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    event = relationship("WazuhEvent", back_populates="suppressions")
    acknowledged_by = relationship("User", foreign_keys=[acknowledged_by_id])


class EventRisk(Base):
    """
    Event Risk Scoring Data.
    
    Stores calculated risk scores and contributing factors for events.
    Enables trending, threshold alerting, and endpoint risk calculation.
    """
    __tablename__ = "event_risks"
    __table_args__ = (
        Index("idx_risk_agent_id", "agent_id"),
        Index("idx_risk_endpoint_risk", "endpoint_risk_score"),
        Index("idx_risk_user_risk", "user_risk_score"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("wazuh_events.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # Event context
    agent_id: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    source_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    source_user: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Risk Components
    base_risk_score: Mapped[float] = mapped_column(Float, default=0.0)  # Rule severity
    severity_factor: Mapped[float] = mapped_column(Float, default=1.0)  # 0-10 multiplier
    frequency_factor: Mapped[float] = mapped_column(Float, default=1.0)  # How common is this?
    recency_factor: Mapped[float] = mapped_column(Float, default=1.0)  # How recent?
    
    # Calculated Scores
    event_risk_score: Mapped[float] = mapped_column(Float, default=0.0)  # This specific event risk
    endpoint_risk_score: Mapped[float] = mapped_column(Float, default=0.0)  # Agent's risk level
    user_risk_score: Mapped[float] = mapped_column(Float, default=0.0)  # User's risk level
    
    # Risk Flags
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    is_anomalous: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    event = relationship("WazuhEvent", back_populates="risk_record")


class EndpointInventory(Base):
    """
    Wazuh Agent Inventory (Endpoint Information).
    
    Tracks connected agents and their system information.
    Updated from Wazuh API syscollector data.
    """
    __tablename__ = "endpoint_inventory"
    __table_args__ = (
        Index("idx_endpoint_agent_id", "agent_id", unique=True),
        Index("idx_endpoint_status", "status"),
        Index("idx_endpoint_last_seen", "last_keepalive"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Agent IDs
    agent_id: Mapped[str] = mapped_column(String(10), nullable=False, unique=True, index=True)
    agent_name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Agent Status
    status: Mapped[str] = mapped_column(String(20), default="unknown")  # active, disconnected, never_connected, unknown
    last_keepalive: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # System Information
    os_platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    os_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    os_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    hostname: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    
    # Agent Version
    wazuh_agent_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    node_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Custom Metadata
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    
    # Risk Score (cached)
    current_risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    critical_alert_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Sync Information
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
