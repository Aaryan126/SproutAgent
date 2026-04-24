from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.doc_update import DocUpdate


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    doc_update_id: Mapped[int] = mapped_column(
        ForeignKey("doc_updates.id"), nullable=False
    )
    approver: Mapped[str] = mapped_column(String, nullable=False)
    decision: Mapped[str] = mapped_column(String, nullable=False)
    comment: Mapped[str | None] = mapped_column(nullable=True)
    decided_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    doc_update: Mapped["DocUpdate"] = relationship(
        "DocUpdate", back_populates="approvals"
    )


class Config(Base):
    __tablename__ = "config"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
