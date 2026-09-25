"""Empty shell in Phase 1: no code reads or writes this table."""
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.connected_account import ProviderType
from app.models.enums import Provider


class ActivityDebrief(Base):
    __tablename__ = "activity_debriefs"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", "provider_activity_id", name="uq_debrief_activity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    planned_workout_id: Mapped[int | None] = mapped_column(ForeignKey("planned_workouts.id"), nullable=True)
    provider: Mapped[Provider] = mapped_column(ProviderType)
    provider_activity_id: Mapped[str] = mapped_column(String(64))
    compliance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
