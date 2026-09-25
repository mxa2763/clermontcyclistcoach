from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.enums import Provider

# VARCHAR instead of a native DB enum so adding a provider never needs an ALTER TYPE.
ProviderType = Enum(Provider, native_enum=False, create_constraint=False, length=32)


class ConnectedAccount(Base):
    __tablename__ = "connected_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[Provider] = mapped_column(ProviderType)
    provider_athlete_id: Mapped[str] = mapped_column(String(64))
    access_token_encrypted: Mapped[str] = mapped_column(Text)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes_granted: Mapped[str | None] = mapped_column(Text, nullable=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "uq_active_provider_per_user",
            "user_id",
            "provider",
            unique=True,
            sqlite_where=text("revoked_at IS NULL"),
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index(
            "uq_active_athlete_per_provider",
            "provider",
            "provider_athlete_id",
            unique=True,
            sqlite_where=text("revoked_at IS NULL"),
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )
