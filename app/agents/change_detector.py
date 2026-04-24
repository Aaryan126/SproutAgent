import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.claude_client import ClaudeClient
from app.config import Settings
from app.integrations.github_api import GitHubClient
from app.integrations.notion_api import NotionClient
from app.models.approval import Config
from app.models.event import Event

logger = structlog.get_logger()

ENTITY_SYSTEM_PROMPT = """You are an expert at analyzing software changes to identify
documentation that needs updating. Your job is to generate search terms that will find
the relevant sections in EXISTING documentation — which still reflects the old state
before this PR. Always return valid JSON."""

SCORING_SYSTEM_PROMPT = """You are a documentation quality reviewer. Determine with high
precision whether a documentation file contains outdated information based on a code change.
Prefer false negatives over false positives — only flag docs that clearly need updating.
When you identify a section to update, return the exact verbatim text from the doc as
original_section so it can be used for string replacement. Always return valid JSON."""


class ChangeDetector:
    def __init__(
        self,
        claude: ClaudeClient,
        github: GitHubClient,
        notion: NotionClient,
        settings: Settings,
    ) -> None:
        self._claude = claude
        self._github = github
        self._notion = notion
        self._settings = settings

    async def analyze_event(self, event: Event, db: AsyncSession) -> list[dict]:
        logger.info("change_detector_start", event_id=event.id)

        pr_payload = event.raw_payload.get("pull_request", {})
        pr_context = self._format_pr_for_prompt(pr_payload)

        entities = await self._extract_entities(pr_context)
        event.entities = entities
        await db.flush()
        logger.info("entities_extracted", event_id=event.id, entities=entities)

        docs = await self._search_all_docs(entities)
        logger.info("docs_found", event_id=event.id, count=len(docs))

        threshold = await self._get_confidence_threshold(db)
        updates = []
        for doc in docs:
            analysis = await self._score_doc(pr_context, doc, threshold)
            if analysis:
                updates.append({
                    "doc": doc,
                    "analysis": analysis,
                })
                logger.info(
                    "doc_needs_update",
                    path=doc["path"],
                    confidence=analysis["confidence"],
                )

        logger.info("change_detector_done", event_id=event.id, updates=len(updates))
        return updates

    async def _extract_entities(self, pr_context: str) -> dict:
        prompt = f"""Analyze this PR and generate search terms to find affected documentation.

PR Details:
{pr_context}

Generate terms that would appear in EXISTING docs (before this PR changed anything).
For example: if a PR increases a rate limit from 100 to 200, search for "rate limit"
or "requests per minute" — NOT "200/min" (existing docs still say the old value).
If a PR adds OAuth support, search for "authentication" or "API key", not "OAuth 2.0"
(existing docs don't mention OAuth yet).

Return JSON:
{{
    "endpoints": ["API path patterns like /api/v2/users, /webhook"],
    "features": ["concept or feature names like 'rate limiting', 'authentication', 'SSO'"],
    "config_values": ["config topic phrases like 'requests per minute', 'timeout', 'rate limit'"],
    "terms": ["technical terms an existing doc would contain: 'API key', 'webhook', 'bearer token'"],
    "products": ["product or integration names"]
}}

Prefer short, broad phrases over specific new values. Return empty lists where not applicable."""

        try:
            response = await self._claude.generate(
                user_prompt=prompt,
                system_prompt=ENTITY_SYSTEM_PROMPT,
                cache_system_prompt=True,
            )
            return ClaudeClient.parse_json_response(response)
        except (ValueError, Exception) as e:
            logger.error("entity_extraction_failed", error=str(e))
            return {"endpoints": [], "features": [], "config_values": [], "terms": [], "products": []}

    async def _search_all_docs(self, entities: dict) -> list[dict]:
        seen: dict[str, dict] = {}

        search_terms = []
        for category, values in entities.items():
            search_terms.extend(values[:3])

        for term in search_terms[:10]:
            if not term:
                continue
            try:
                results = await self._github.search_docs(
                    query=term,
                    docs_repo=self._settings.docs_repo,
                )
                for r in results:
                    if r["path"] not in seen:
                        seen[r["path"]] = r
            except Exception as e:
                logger.warning("doc_search_failed", term=term, error=str(e))

        try:
            notion_pages = await self._notion.list_all_pages()
            for r in notion_pages:
                key = r["path"]
                if key not in seen:
                    seen[key] = r
        except Exception as e:
            logger.warning("notion_list_failed", error=str(e))

        return list(seen.values())

    async def _score_doc(
        self, pr_context: str, doc: dict, threshold: float
    ) -> dict | None:
        doc_content = doc.get("content", "")
        if len(doc_content) > 8000:
            doc_content = doc_content[:8000] + "\n... [truncated]"

        prompt = f"""Analyze whether this documentation needs updating based on the PR.

PR CONTEXT:
{pr_context}

DOCUMENTATION:
Path: {doc['path']}
Content:
```
{doc_content}
```

Return JSON:
{{
    "needs_update": true or false,
    "confidence": 0.0 to 1.0,
    "change_type": "add" | "modify" | "remove" | "deprecate",
    "section_identifier": "description of which section",
    "evidence": {{
        "event_signals": ["what in the PR suggests this update"],
        "doc_issues": ["what in the doc is now outdated"],
        "reasoning": "brief explanation"
    }},
    "original_section": "exact verbatim text from the doc to replace",
    "suggested_content": "replacement text"
}}

Confidence guide:
- 0.9-1.0: Explicit mention, clear factual mismatch
- 0.7-0.9: Strongly implied, likely outdated
- 0.5-0.7: Possibly outdated, worth human review
- <0.5: Unclear, probably fine

If needs_update is false, return {{"needs_update": false, "confidence": 0.0}}"""

        try:
            response = await self._claude.generate(
                user_prompt=prompt,
                system_prompt=SCORING_SYSTEM_PROMPT,
                cache_system_prompt=True,
            )
            analysis = ClaudeClient.parse_json_response(response)
        except (ValueError, Exception) as e:
            logger.error("doc_scoring_failed", path=doc["path"], error=str(e))
            return None

        if not analysis.get("needs_update"):
            return None
        if analysis.get("confidence", 0.0) < threshold:
            return None
        if not analysis.get("original_section"):
            return None

        return analysis

    async def _get_confidence_threshold(self, db: AsyncSession) -> float:
        try:
            result = await db.execute(
                select(Config).where(Config.key == "confidence_threshold")
            )
            config_row = result.scalar_one_or_none()
            if config_row is not None:
                return float(config_row.value.get("value", self._settings.confidence_threshold))
        except Exception as e:
            logger.warning("config_lookup_failed", error=str(e))
        return self._settings.confidence_threshold

    def _format_pr_for_prompt(self, pr_payload: dict) -> str:
        title = pr_payload.get("title", "")
        body = pr_payload.get("body") or ""
        author = pr_payload.get("user", {}).get("login", "unknown")
        files = pr_payload.get("changed_files", [])
        if isinstance(files, int):
            files_str = f"{files} files changed"
        else:
            files_str = ", ".join(files[:10])

        body_preview = body[:500] + "..." if len(body) > 500 else body

        return f"""Title: {title}
Author: {author}
Changed files: {files_str}
Description:
{body_preview}"""
