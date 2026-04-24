import structlog

logger = structlog.get_logger()


class NotionClient:
    def __init__(self, token: str) -> None:
        self._enabled = bool(token)

    async def search_pages(self, query: str) -> list[dict]:
        if not self._enabled:
            return []
        raise NotImplementedError("Notion integration is phase 2")

    async def get_page_content(self, page_id: str) -> str:
        raise NotImplementedError("Notion integration is phase 2")

    async def update_block(
        self, block_id: str, new_content: str, block_type: str = "paragraph"
    ) -> None:
        raise NotImplementedError("Notion integration is phase 2")
