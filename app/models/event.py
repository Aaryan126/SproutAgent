from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.doc_update import DocUpdate


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    event_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    entities: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    doc_updates: Mapped[list["DocUpdate"]] = relationship(
        "DocUpdate", back_populates="event"
    )

    __table_args__ = (
        UniqueConstraint("event_id", name="uq_events_event_id"),
    )
