import structlog
from notion_client import AsyncClient
from notion_client.errors import APIResponseError

logger = structlog.get_logger()

_RICH_TEXT_BLOCK_TYPES = {
    "paragraph",
    "heading_1",
    "heading_2",
    "heading_3",
    "bulleted_list_item",
    "numbered_list_item",
    "quote",
    "to_do",
    "toggle",
    "callout",
}


class NotionClient:
    def __init__(self, token: str) -> None:
        self._enabled = bool(token)
        self._client = AsyncClient(auth=token) if token else None

    async def search_pages(self, query: str) -> list[dict]:
        return []

    async def list_all_pages(self) -> list[dict]:
        if not self._enabled or self._client is None:
            return []
        try:
            results = await self._client.search(
                filter={"property": "object", "value": "page"},
            )
        except APIResponseError as e:
            logger.warning("notion_list_pages_failed", error=str(e))
            return []

        pages = []
        for page in results.get("results", []):
            page_id = page["id"]
            try:
                content = await self.get_page_content(page_id)
            except Exception as e:
                logger.warning("notion_page_content_failed", page_id=page_id, error=str(e))
                content = ""

            if not content:
                continue

            title = self._extract_title(page)
            pages.append({
                "id": page_id,
                "platform": "notion",
                "path": f"notion:{page_id}",
                "title": title,
                "content": content,
                "html_url": page.get("url", ""),
            })
            logger.info("notion_page_loaded", title=title, page_id=page_id)

        logger.info("notion_pages_loaded", count=len(pages))
        return pages

    async def get_page_content(self, page_id: str) -> str:
        if self._client is None:
            return ""
        response = await self._client.blocks.children.list(block_id=page_id)
        lines = []
        for block in response.get("results", []):
            text = self._block_to_text(block)
            if text:
                lines.append(text)
        return "\n\n".join(lines)

    async def apply_surgical_update(
        self, page_id: str, original_text: str, proposed_text: str
    ) -> bool:
        if self._client is None:
            return False

        response = await self._client.blocks.children.list(block_id=page_id)
        blocks = response.get("results", [])

        original_stripped = original_text.strip()
        proposed_stripped = proposed_text.strip()

        # Try exact single-block match first
        for block in blocks:
            block_text = self._block_to_text(block)
            if block_text and original_stripped in block_text:
                new_text = block_text.replace(original_stripped, proposed_stripped, 1)
                try:
                    await self._update_block_text(block["id"], block["type"], new_text)
                    logger.info("notion_block_updated", page_id=page_id, block_id=block["id"])
                    return True
                except APIResponseError as e:
                    logger.warning("notion_block_update_failed", block_id=block["id"], error=str(e))
                    return False

        # original_text spans multiple blocks — compare line by line and update only changed lines
        original_lines = [l.strip() for l in original_stripped.split("\n\n") if l.strip()]
        proposed_lines = [l.strip() for l in proposed_stripped.split("\n\n") if l.strip()]

        if len(original_lines) > 1 and len(original_lines) == len(proposed_lines):
            updated = 0
            for orig_line, prop_line in zip(original_lines, proposed_lines):
                if orig_line == prop_line:
                    continue
                for block in blocks:
                    block_text = self._block_to_text(block)
                    if block_text and orig_line in block_text:
                        new_text = block_text.replace(orig_line, prop_line, 1)
                        try:
                            await self._update_block_text(block["id"], block["type"], new_text)
                            logger.info("notion_block_updated", page_id=page_id, block_id=block["id"], line=orig_line[:60])
                            updated += 1
                        except APIResponseError as e:
                            logger.warning("notion_block_update_failed", block_id=block["id"], error=str(e))
                        break
            if updated > 0:
                return True

        logger.warning(
            "notion_original_text_not_found",
            page_id=page_id,
            original_text=original_stripped[:120],
        )
        return False

    def _block_to_text(self, block: dict) -> str:
        block_type = block.get("type", "")
        if block_type not in _RICH_TEXT_BLOCK_TYPES:
            return ""
        rich_text = block.get(block_type, {}).get("rich_text", [])
        return "".join(t.get("plain_text", "") for t in rich_text)

    async def _update_block_text(self, block_id: str, block_type: str, new_text: str) -> None:
        await self._client.blocks.update(
            block_id=block_id,
            **{
                block_type: {
                    "rich_text": [{"type": "text", "text": {"content": new_text}}]
                }
            },
        )

    def _extract_title(self, page: dict) -> str:
        try:
            for prop in page.get("properties", {}).values():
                if prop.get("type") == "title":
                    return "".join(t.get("plain_text", "") for t in prop.get("title", []))
        except Exception:
            pass
        return "Untitled"
