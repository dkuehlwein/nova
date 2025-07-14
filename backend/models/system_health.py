"""
System Health Status Database Model

Cached system health status with historical data for unified monitoring.
Follows ADR 010 unified system health monitoring architecture.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from uuid import uuid4

from sqlalchemy import String, Integer, Text, DateTime, Index, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB

from models.models import Base


class SystemHealthStatus(Base):
    """Cached system health status with historical data."""
    __tablename__ = 'system_health_status'
    
    id: Mapped[str] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    service_name: Mapped[str] = mapped_column(String(100), nullable=False)  # "core_agent", "chat_agent", etc.
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # "healthy", "degraded", "unhealthy"
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    service_metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_service_checked_at', 'service_name', 'checked_at'),
        Index('idx_service_latest', 'service_name', 'created_at'),
        Index('idx_status_time', 'status', 'checked_at'),
    )

    def __repr__(self):
        return f"<SystemHealthStatus(service={self.service_name}, status={self.status}, checked_at={self.checked_at})>"