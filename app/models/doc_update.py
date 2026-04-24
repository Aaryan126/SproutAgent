from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.approval import Approval
    from app.models.event import Event


class DocUpdateStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"


class ChangeType(str, Enum):
    ADD = "add"
    MODIFY = "modify"
    REMOVE = "remove"
    DEPRECATE = "deprecate"


class DocUpdate(Base):
    __tablename__ = "doc_updates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    doc_platform: Mapped[str] = mapped_column(String, nullable=False)
    doc_path: Mapped[str] = mapped_column(String, nullable=False)
    doc_section: Mapped[str | None] = mapped_column(String, nullable=True)
    change_type: Mapped[str] = mapped_column(String, nullable=False)
    original_content: Mapped[str | None] = mapped_column(nullable=True)
    proposed_content: Mapped[str] = mapped_column(nullable=False)
    diff_markdown: Mapped[str] = mapped_column(nullable=False)
    confidence_score: Mapped[float] = mapped_column(nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String, default=DocUpdateStatus.PENDING)
    assigned_to: Mapped[str | None] = mapped_column(String, nullable=True)
    github_pr_url: Mapped[str | None] = mapped_column(String, nullable=True)
    notion_page_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(nullable=True)

    event: Mapped["Event"] = relationship("Event", back_populates="doc_updates")
    approvals: Mapped[list["Approval"]] = relationship(
        "Approval", back_populates="doc_update"
    )
