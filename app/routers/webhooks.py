import json
from datetime import datetime

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.approver_router import ApproverRouter
from app.agents.change_detector import ChangeDetector
from app.agents.claude_client import ClaudeClient
from app.agents.update_generator import UpdateGenerator
from app.config import settings
from app.database import AsyncSessionLocal, get_db
from app.integrations.github_api import GitHubClient
from app.integrations.notion_api import NotionClient
from app.models.doc_update import DocUpdate, DocUpdateStatus
from app.models.event import Event
from app.utils.signature_validator import validate_github_signature

router = APIRouter(prefix="/webhook", tags=["webhooks"])
logger = structlog.get_logger()


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
    x_github_delivery: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    body = await request.body()

    try:
        valid = validate_github_signature(body, x_hub_signature_256, settings.github_webhook_secret)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    if not valid:
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = json.loads(body)

    if x_github_event != "pull_request":
        return {"status": "ignored", "reason": f"event type '{x_github_event}' not handled"}

    pr = payload.get("pull_request", {})
    if payload.get("action") != "closed" or not pr.get("merged"):
        return {"status": "ignored", "reason": "PR not merged"}

    event_id = x_github_delivery or str(pr.get("id", ""))

    existing = await db.execute(select(Event).where(Event.event_id == event_id))
    if existing.scalar_one_or_none():
        return {"status": "duplicate", "event_id": event_id}

    event = Event(
        source="github",
        event_type="pull_request",
        event_id=event_id,
        raw_payload=payload,
    )
    db.add(event)
    await db.flush()

    logger.info("webhook_received", event_id=event.id, pr_number=pr.get("number"))

    background_tasks.add_task(process_pr_event, event.id)

    return {"status": "received", "event_id": event.id}


async def process_pr_event(event_id: int) -> None:
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(Event).where(Event.id == event_id))
            event = result.scalar_one_or_none()
            if not event:
                logger.error("event_not_found", event_id=event_id)
                return

            logger.info("processing_start", event_id=event_id)

            github = GitHubClient(settings.github_token, settings.github_repo)
            notion = NotionClient(settings.notion_token)
            claude = ClaudeClient(settings.anthropic_api_key)

            detector = ChangeDetector(claude, github, notion, settings)
            updates = await detector.analyze_event(event, db)

            if not updates:
                logger.info("no_updates_needed", event_id=event_id)
                event.processed_at = datetime.utcnow()
                await db.commit()
                return

            generator = UpdateGenerator(claude)
            approver_router = ApproverRouter(github, settings)

            for update_data in updates:
                doc = update_data["doc"]
                analysis = update_data["analysis"]

                try:
                    generated = await generator.generate_update(event, doc, analysis)
                except ValueError as e:
                    logger.warning(
                        "update_generation_skipped",
                        path=doc["path"],
                        error=str(e),
                    )
                    continue

                approver = await approver_router.get_approver(event, doc["path"])

                pr_url = None
                try:
                    pr_url = await github.create_doc_update_pr(
                        file_path=doc["path"],
                        new_content=generated["full_new_file"],
                        branch_name="",
                        pr_title=generated["pr_title"],
                        pr_body=generated["pr_body"],
                        reviewer=approver,
                        event_id=str(event_id),
                    )
                    logger.info("doc_pr_created", url=pr_url, path=doc["path"])
                except Exception as e:
                    logger.error("doc_pr_creation_failed", path=doc["path"], error=str(e))

                doc_update = DocUpdate(
                    event_id=event.id,
                    doc_platform=doc.get("platform", "github"),
                    doc_path=doc["path"],
                    doc_section=analysis.get("section_identifier"),
                    change_type=analysis.get("change_type", "modify"),
                    original_content=analysis.get("original_section"),
                    proposed_content=generated["proposed_content"],
                    diff_markdown=generated["diff_markdown"],
                    confidence_score=analysis["confidence"],
                    evidence=analysis.get("evidence", {}),
                    status=DocUpdateStatus.PENDING,
                    assigned_to=approver,
                    github_pr_url=pr_url,
                )
                db.add(doc_update)

            event.processed_at = datetime.utcnow()
            await db.commit()
            logger.info("processing_done", event_id=event_id, updates=len(updates))

        except Exception as e:
            logger.error("processing_failed", event_id=event_id, error=str(e), exc_info=True)
            try:
                await db.rollback()
            except Exception:
                pass
