from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

class Game(Base):
    __tablename__ = 'games'
    
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default='active'
    )

    ships: Mapped[list[dict[str, list[str]]]] = mapped_column(
        JSONB,
        nullable=False
    )

    own_shots: Mapped[dict[str, str]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict
    )

    opponent_shots: Mapped[dict[str, str]] = mapped_column(
       JSONB,
       nullable=False,
       default=dict
    )

    target_hits: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list
    )

    pending_shot: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
        default=None
    )

    turn: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default='unknown'
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )