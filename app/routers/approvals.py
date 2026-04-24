from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.approval import Approval
from app.models.doc_update import DocUpdate, DocUpdateStatus

router = APIRouter(prefix="/approvals", tags=["approvals"])
logger = structlog.get_logger()


class ApprovalRequest(BaseModel):
    approver: str
    decision: str
    comment: str | None = None


def _serialize_doc_update(u: DocUpdate) -> dict:
    return {
        "id": u.id,
        "event_id": u.event_id,
        "doc_platform": u.doc_platform,
        "doc_path": u.doc_path,
        "doc_section": u.doc_section,
        "change_type": u.change_type,
        "confidence_score": u.confidence_score,
        "status": u.status,
        "assigned_to": u.assigned_to,
        "github_pr_url": u.github_pr_url,
        "diff_markdown": u.diff_markdown,
        "evidence": u.evidence,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "approved_at": u.approved_at.isoformat() if u.approved_at else None,
    }


@router.get("/")
async def list_approvals(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    query = select(DocUpdate).order_by(DocUpdate.created_at.desc())
    if status:
        query = query.where(DocUpdate.status == status)
    result = await db.execute(query)
    return [_serialize_doc_update(u) for u in result.scalars().all()]


@router.get("/{doc_update_id}")
async def get_approval(
    doc_update_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(DocUpdate).where(DocUpdate.id == doc_update_id)
    )
    update = result.scalar_one_or_none()
    if not update:
        raise HTTPException(status_code=404, detail="Doc update not found")
    return _serialize_doc_update(update)


@router.post("/{doc_update_id}/decide")
async def record_decision(
    doc_update_id: int,
    body: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    if body.decision not in ("approved", "rejected"):
        raise HTTPException(
            status_code=400, detail="decision must be 'approved' or 'rejected'"
        )

    result = await db.execute(
        select(DocUpdate).where(DocUpdate.id == doc_update_id)
    )
    update = result.scalar_one_or_none()
    if not update:
        raise HTTPException(status_code=404, detail="Doc update not found")

    approval = Approval(
        doc_update_id=doc_update_id,
        approver=body.approver,
        decision=body.decision,
        comment=body.comment,
        decided_at=datetime.utcnow(),
    )
    db.add(approval)

    update.status = body.decision
    if body.decision == "approved":
        update.approved_at = datetime.utcnow()

    logger.info(
        "approval_recorded",
        doc_update_id=doc_update_id,
        decision=body.decision,
        approver=body.approver,
    )

    return {"status": "recorded", "doc_update_id": doc_update_id, "decision": body.decision}
