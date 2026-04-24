import asyncio
import time
from collections.abc import Callable
from typing import Any

import structlog
from github import Github, GithubException

logger = structlog.get_logger()

_DOC_DIRS = {"docs", "documentation", "doc"}


class GitHubClient:
    def __init__(self, token: str, repo_name: str) -> None:
        self._token = token
        self._gh = Github(token)
        self._repo_name = repo_name

    async def get_pr_details(self, pr_number: int) -> dict:
        repo = await self._run_sync(self._gh.get_repo, self._repo_name)
        pr = await self._run_sync(repo.get_pull, pr_number)
        files = await self._run_sync(pr.get_files)
        return {
            "number": pr.number,
            "title": pr.title,
            "body": pr.body or "",
            "author": pr.user.login,
            "html_url": pr.html_url,
            "merged": pr.merged,
            "changed_files": [f.filename for f in files],
        }

    async def search_docs(
        self, query: str, docs_repo: str | None = None
    ) -> list[dict]:
        repo_name = docs_repo or self._repo_name

        def _sync_search() -> list[dict]:
            gh = Github(self._token)
            logger.info("github_search_docs", repo=repo_name, query=query)
            try:
                repo = gh.get_repo(repo_name)
            except GithubException as e:
                logger.warning("github_get_repo_failed", repo=repo_name, error=str(e))
                return []

            results: dict[str, dict] = {}

            try:
                root_contents = repo.get_contents("/")
            except GithubException as e:
                logger.warning("github_root_contents_failed", repo=repo_name, error=str(e))
                return []

            if not isinstance(root_contents, list):
                root_contents = [root_contents]

            for item in root_contents:
                if item.type == "dir" and item.path in _DOC_DIRS:
                    for r in self._sync_search_directory(repo, item.path, query):
                        results.setdefault(r["path"], r)
                elif item.path.endswith(".md"):
                    doc = self._sync_load_and_filter(item, query)
                    if doc:
                        results.setdefault(doc["path"], doc)

            return list(results.values())

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_search)

    def _sync_search_directory(self, repo: Any, dir_path: str, query: str) -> list[dict]:
        results = []
        try:
            contents = repo.get_contents(dir_path)
            if not isinstance(contents, list):
                contents = [contents]
            for item in contents:
                if item.type == "dir":
                    results.extend(self._sync_search_directory(repo, item.path, query))
                elif item.path.endswith(".md"):
                    doc = self._sync_load_and_filter(item, query)
                    if doc:
                        results.append(doc)
        except GithubException as e:
            logger.warning("github_dir_search_failed", path=dir_path, error=str(e))
        return results

    def _sync_load_and_filter(self, item: Any, query: str) -> dict | None:
        try:
            content = item.decoded_content.decode("utf-8", errors="replace")
            if query.lower() in content.lower():
                return {
                    "path": item.path,
                    "content": content,
                    "sha": item.sha,
                    "html_url": item.html_url,
                }
        except Exception as e:
            logger.warning("github_file_load_failed", path=item.path, error=str(e))
        return None

    async def get_file_content(
        self, path: str, ref: str = "main"
    ) -> tuple[str, str]:
        repo = await self._run_sync(self._gh.get_repo, self._repo_name)
        file_obj = await self._run_sync(repo.get_contents, path, ref=ref)
        content = file_obj.decoded_content.decode("utf-8", errors="replace")
        return content, file_obj.sha

    async def create_doc_update_pr(
        self,
        file_path: str,
        new_content: str,
        branch_name: str,
        pr_title: str,
        pr_body: str,
        reviewer: str,
        event_id: str = "",
    ) -> str:
        repo = await self._run_sync(self._gh.get_repo, self._repo_name)
        branch = f"docs-agent/update-{event_id}-{int(time.time())}" if not branch_name else branch_name

        default_branch = await self._run_sync(lambda: repo.default_branch)
        base_ref = await self._run_sync(
            repo.get_git_ref, f"heads/{default_branch}"
        )
        await self._run_sync(
            repo.create_git_ref,
            ref=f"refs/heads/{branch}",
            sha=base_ref.object.sha,
        )

        try:
            file_obj = await self._run_sync(
                repo.get_contents, file_path, ref=default_branch
            )
            await self._run_sync(
                repo.update_file,
                path=file_path,
                message=f"docs: {pr_title}",
                content=new_content,
                sha=file_obj.sha,
                branch=branch,
            )
        except GithubException:
            await self._run_sync(
                repo.create_file,
                path=file_path,
                message=f"docs: {pr_title}",
                content=new_content,
                branch=branch,
            )

        pr = await self._run_sync(
            repo.create_pull,
            title=f"[Docs] {pr_title}",
            body=pr_body,
            head=branch,
            base=default_branch,
        )

        try:
            await self._run_sync(pr.create_review_request, reviewers=[reviewer])
        except GithubException as e:
            logger.warning("review_request_failed", reviewer=reviewer, error=str(e))

        try:
            await self._run_sync(pr.add_to_labels, "documentation", "automated")
        except GithubException as e:
            logger.warning("label_failed", error=str(e))

        return pr.html_url

    async def get_codeowners_content(self) -> str | None:
        try:
            content, _ = await self.get_file_content(".github/CODEOWNERS")
            return content
        except GithubException:
            return None

    async def _run_sync(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))
