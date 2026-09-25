"""Empty shell in Phase 1: no code reads or writes this table."""
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PlannedWorkout(Base):
    __tablename__ = "planned_workouts"
    __table_args__ = (UniqueConstraint("user_id", "source_event_id", name="uq_planned_workout_source_event"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    scheduled_date: Mapped[date] = mapped_column(Date, index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    structure: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # Intervals.icu event id
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
