import fnmatch

import structlog

from app.config import Settings
from app.integrations.github_api import GitHubClient
from app.models.event import Event

logger = structlog.get_logger()


class ApproverRouter:
    def __init__(self, github: GitHubClient, settings: Settings) -> None:
        self._github = github
        self._settings = settings
        self._codeowners: dict[str, list[str]] = {}
        self._codeowners_loaded = False

    async def get_approver(self, event: Event, doc_path: str) -> str:
        pr_payload = event.raw_payload.get("pull_request", {})
        author = pr_payload.get("user", {}).get("login")
        if author:
            logger.info("approver_pr_author", approver=author)
            return author

        if not self._codeowners_loaded:
            await self._load_codeowners()

        owner = self._match_codeowner(doc_path)
        if owner:
            logger.info("approver_codeowners", approver=owner, path=doc_path)
            return owner

        logger.info("approver_default", approver=self._settings.default_approver)
        return self._settings.default_approver

    async def _load_codeowners(self) -> None:
        self._codeowners_loaded = True
        try:
            content = await self._github.get_codeowners_content()
            if not content:
                return
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) < 2:
                    continue
                pattern = parts[0]
                owners = [o.lstrip("@") for o in parts[1:]]
                self._codeowners[pattern] = owners
        except Exception as e:
            logger.warning("codeowners_load_failed", error=str(e))

    def _match_codeowner(self, doc_path: str) -> str | None:
        for pattern, owners in self._codeowners.items():
            if fnmatch.fnmatch(doc_path, pattern) or fnmatch.fnmatch(f"/{doc_path}", pattern):
                return owners[0] if owners else None
        return None
