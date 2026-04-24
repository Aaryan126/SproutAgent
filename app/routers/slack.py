import hashlib
import hmac
import json
import time
from datetime import datetime
from urllib.parse import parse_qs

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.integrations.github_api import GitHubClient
from app.integrations.notion_api import NotionClient
from app.integrations.slack_api import SlackClient
from app.models.approval import Approval
from app.models.doc_update import DocUpdate, DocUpdateStatus
from app.routers.approvals import _parse_github_pr_url

router = APIRouter(prefix="/slack", tags=["slack"])
logger = structlog.get_logger()


def _verify_slack_signature(body: bytes, timestamp: str, signature: str, secret: str) -> bool:
    if abs(time.time() - int(timestamp)) > 300:
        return False
    base = f"v0:{timestamp}:{body.decode()}"
    expected = "v0=" + hmac.new(secret.encode(), base.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/interactivity")
async def slack_interactivity(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "0")
    signature = request.headers.get("X-Slack-Signature", "")

    if settings.slack_signing_secret:
        if not _verify_slack_signature(body, timestamp, signature, settings.slack_signing_secret):
            raise HTTPException(status_code=401, detail="Invalid Slack signature")

    form = parse_qs(body.decode())
    payload_str = form.get("payload", ["{}"])[0]
    data = json.loads(payload_str)
    action = data.get("actions", [{}])[0]
    action_id = action.get("action_id", "")
    doc_update_id = int(action.get("value", 0))
    user = data.get("user", {}).get("username", "slack-user")
    message_ts = data.get("message", {}).get("ts")
    channel_id = data.get("channel", {}).get("id")

    if action_id not in ("approve_doc_update", "reject_doc_update"):
        return {"ok": True}

    decision = "approved" if action_id == "approve_doc_update" else "rejected"

    result = await db.execute(select(DocUpdate).where(DocUpdate.id == doc_update_id))
    update = result.scalar_one_or_none()
    if not update:
        logger.warning("slack_doc_update_not_found", doc_update_id=doc_update_id)
        return {"ok": True}

    if update.status != DocUpdateStatus.PENDING:
        logger.info("slack_already_decided", doc_update_id=doc_update_id, status=update.status)
        return {"ok": True}

    approval = Approval(
        doc_update_id=doc_update_id,
        approver=user,
        decision=decision,
        decided_at=datetime.utcnow(),
    )
    db.add(approval)
    update.status = decision
    if decision == "approved":
        update.approved_at = datetime.utcnow()
    await db.commit()

    if decision == "approved":
        if update.github_pr_url:
            try:
                repo_name, pr_number = _parse_github_pr_url(update.github_pr_url)
                gh = GitHubClient(settings.github_token, repo_name)
                merged = await gh.merge_pr(pr_number)
                if merged:
                    update.status = "applied"
                    update.applied_at = datetime.utcnow()
                    await db.commit()
                    logger.info("slack_github_pr_merged", doc_update_id=doc_update_id)
            except Exception as e:
                logger.warning("slack_github_merge_failed", error=str(e))

        elif update.doc_platform == "notion" and update.original_content and update.proposed_content:
            try:
                page_id = update.doc_path.replace("notion:", "")
                notion = NotionClient(settings.notion_token)
                applied = await notion.apply_surgical_update(
                    page_id=page_id,
                    original_text=update.original_content,
                    proposed_text=update.proposed_content,
                )
                if applied:
                    update.status = "applied"
                    update.applied_at = datetime.utcnow()
                    await db.commit()
                    logger.info("slack_notion_updated", doc_update_id=doc_update_id)
            except Exception as e:
                logger.warning("slack_notion_update_failed", error=str(e))

    slack = SlackClient(settings.slack_bot_token, settings.slack_channel)
    if message_ts and channel_id:
        await slack.update_message_decided(channel_id, message_ts, decision, user)

    logger.info("slack_decision_recorded", doc_update_id=doc_update_id, decision=decision, user=user)
    return {"ok": True}
