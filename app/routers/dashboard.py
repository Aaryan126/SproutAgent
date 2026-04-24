from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.doc_update import DocUpdate
from app.models.event import Event

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/")
async def dashboard_summary(db: AsyncSession = Depends(get_db)) -> dict:
    total_events = await db.scalar(select(func.count(Event.id)))

    status_rows = await db.execute(
        select(DocUpdate.status, func.count(DocUpdate.id)).group_by(DocUpdate.status)
    )
    status_counts = {row[0]: row[1] for row in status_rows.all()}

    recent_result = await db.execute(
        select(DocUpdate).order_by(DocUpdate.created_at.desc()).limit(5)
    )
    recent = [
        {
            "id": u.id,
            "doc_path": u.doc_path,
            "confidence_score": u.confidence_score,
            "status": u.status,
            "github_pr_url": u.github_pr_url,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in recent_result.scalars().all()
    ]

    return {
        "total_events_processed": total_events or 0,
        "doc_updates_by_status": status_counts,
        "recent_updates": recent,
    }


@router.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
