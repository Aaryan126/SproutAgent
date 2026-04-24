import structlog
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

logger = structlog.get_logger()


class SlackClient:
    def __init__(self, token: str, channel: str) -> None:
        self._enabled = bool(token and channel)
        self._client = AsyncWebClient(token=token) if token else None
        self._channel = channel

    async def send_doc_update_notification(self, doc_update: dict) -> str | None:
        if not self._enabled or self._client is None:
            return None

        doc_path = doc_update.get("doc_path", "")
        platform = doc_update.get("doc_platform", "github")
        confidence = int((doc_update.get("confidence_score") or 0) * 100)
        change_type = doc_update.get("change_type", "modify")
        doc_update_id = doc_update.get("id")
        section = doc_update.get("doc_section", "")
        assigned_to = doc_update.get("assigned_to", "")

        platform_label = "Notion" if platform == "notion" else "GitHub"
        display_path = section or (doc_path.replace("notion:", "")[:30] + "…" if platform == "notion" else doc_path)

        evidence = doc_update.get("evidence") or {}
        reasoning = evidence.get("reasoning", "")
        doc_issues = evidence.get("doc_issues", [])
        issue_text = doc_issues[0] if doc_issues else reasoning

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "📄 Doc Update Needed", "emoji": True},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Platform:*\n{platform_label}"},
                    {"type": "mrkdwn", "text": f"*File:*\n`{display_path}`"},
                    {"type": "mrkdwn", "text": f"*Change type:*\n{change_type}"},
                    {"type": "mrkdwn", "text": f"*Confidence:*\n{confidence}%"},
                ],
            },
        ]

        if issue_text:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Why:* {issue_text}"},
            })

        if assigned_to:
            blocks.append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"Assigned to *@{assigned_to}*"}],
            })

        blocks.append({"type": "divider"})
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Approve", "emoji": True},
                    "style": "primary",
                    "action_id": "approve_doc_update",
                    "value": str(doc_update_id),
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ Reject", "emoji": True},
                    "style": "danger",
                    "action_id": "reject_doc_update",
                    "value": str(doc_update_id),
                },
            ],
        })

        try:
            resp = await self._client.chat_postMessage(
                channel=self._channel,
                text=f"Doc update needed for `{display_path}` ({confidence}% confidence)",
                blocks=blocks,
            )
            ts = resp["ts"]
            logger.info("slack_notification_sent", doc_update_id=doc_update_id, ts=ts)
            return ts
        except SlackApiError as e:
            logger.warning("slack_notification_failed", doc_update_id=doc_update_id, error=str(e))
            return None

    async def update_message_decided(
        self, channel: str, ts: str, decision: str, approver: str
    ) -> None:
        if not self._enabled or self._client is None:
            return
        emoji = "✅" if decision == "approved" else "❌"
        text = f"{emoji} *{decision.capitalize()}* by @{approver}"
        try:
            await self._client.chat_update(
                channel=channel,
                ts=ts,
                text=text,
                blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": text}}],
            )
        except SlackApiError as e:
            logger.warning("slack_update_failed", ts=ts, error=str(e))
