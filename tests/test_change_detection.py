import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.claude_client import ClaudeClient
from app.agents.change_detector import ChangeDetector
from app.utils.diff_generator import apply_section_replacement, generate_diff


# ---------------------------------------------------------------------------
# Unit tests: ClaudeClient JSON parsing
# ---------------------------------------------------------------------------

def test_strip_json_fences_with_json_label():
    raw = '```json\n{"key": "value"}\n```'
    result = ClaudeClient.strip_json_fences(raw)
    assert result == '{"key": "value"}'


def test_strip_json_fences_without_label():
    raw = '```\n{"key": "value"}\n```'
    result = ClaudeClient.strip_json_fences(raw)
    assert result == '{"key": "value"}'


def test_strip_json_fences_no_fences():
    raw = '{"key": "value"}'
    result = ClaudeClient.strip_json_fences(raw)
    assert result == '{"key": "value"}'


def test_parse_json_response_success():
    raw = '```json\n{"needs_update": true, "confidence": 0.9}\n```'
    result = ClaudeClient.parse_json_response(raw)
    assert result["needs_update"] is True
    assert result["confidence"] == 0.9


def test_parse_json_response_invalid_raises():
    with pytest.raises(ValueError, match="Failed to parse"):
        ClaudeClient.parse_json_response("not valid json at all")


# ---------------------------------------------------------------------------
# Unit tests: diff_generator utilities
# ---------------------------------------------------------------------------

def test_generate_diff_shows_changes():
    original = "Rate limit: 100 requests per minute\n"
    proposed = "Rate limit: 200 requests per minute\n"
    diff = generate_diff(original, proposed)
    assert "```diff" in diff
    assert "-Rate limit: 100" in diff
    assert "+Rate limit: 200" in diff


def test_apply_section_replacement_success():
    full_doc = "# Intro\n\nRate limit: 100 requests per minute\n\n# End"
    original = "Rate limit: 100 requests per minute"
    proposed = "Rate limit: 200 requests per minute"
    result = apply_section_replacement(full_doc, original, proposed)
    assert "Rate limit: 200 requests per minute" in result
    assert "Rate limit: 100 requests per minute" not in result


def test_apply_section_replacement_not_found():
    with pytest.raises(ValueError, match="Section not found"):
        apply_section_replacement("some doc content", "nonexistent text", "replacement")


def test_apply_section_replacement_only_replaces_first():
    full_doc = "limit: 100\nlimit: 100"
    result = apply_section_replacement(full_doc, "limit: 100", "limit: 200")
    assert result == "limit: 200\nlimit: 100"


# ---------------------------------------------------------------------------
# Integration tests: ChangeDetector with mocked Claude
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_claude():
    claude = MagicMock(spec=ClaudeClient)
    claude.generate = AsyncMock()
    return claude


@pytest.fixture
def mock_github():
    gh = MagicMock()
    gh.search_docs = AsyncMock(return_value=[
        {
            "path": "docs/api.md",
            "content": "# API Docs\n\nRate limit: 100 requests per minute\n",
            "sha": "abc123",
            "html_url": "https://github.com/owner/repo/blob/main/docs/api.md",
        }
    ])
    return gh


@pytest.fixture
def mock_notion():
    notion = MagicMock()
    notion.search_pages = AsyncMock(return_value=[])
    return notion


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.confidence_threshold = 0.5
    settings.docs_repo = "owner/repo"
    settings.notion_token = ""
    return settings


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    db.flush = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_extract_entities_from_rate_limit_pr(
    mock_claude, mock_github, mock_notion, mock_settings, mock_db
):
    entity_response = json.dumps({
        "endpoints": [],
        "features": ["rate limiting"],
        "config_values": ["200 requests per minute", "100/min"],
        "terms": ["rate limit"],
        "products": [],
    })
    scoring_response = json.dumps({
        "needs_update": False,
        "confidence": 0.0,
    })
    mock_claude.generate = AsyncMock(side_effect=[entity_response, scoring_response])

    detector = ChangeDetector(mock_claude, mock_github, mock_notion, mock_settings)

    from app.models.event import Event
    event = MagicMock(spec=Event)
    event.id = 1
    event.raw_payload = {
        "pull_request": {
            "title": "Increase API rate limit to 200/min",
            "body": "Changed from 100 to 200 requests/min",
            "user": {"login": "alice"},
            "changed_files": ["src/rate_limiter.py"],
        }
    }
    event.entities = None

    await detector.analyze_event(event, mock_db)
    assert mock_claude.generate.called


@pytest.mark.asyncio
async def test_score_doc_above_threshold(
    mock_claude, mock_github, mock_notion, mock_settings
):
    scoring_response = json.dumps({
        "needs_update": True,
        "confidence": 0.92,
        "change_type": "modify",
        "section_identifier": "Rate Limits section",
        "evidence": {
            "event_signals": ["PR changed rate limit from 100 to 200"],
            "doc_issues": ["Doc still says 100 requests/min"],
            "reasoning": "Direct numerical mismatch",
        },
        "original_section": "Rate limit: 100 requests per minute",
        "suggested_content": "Rate limit: 200 requests per minute",
    })
    mock_claude.generate = AsyncMock(return_value=scoring_response)

    detector = ChangeDetector(mock_claude, mock_github, mock_notion, mock_settings)
    doc = {
        "path": "docs/api.md",
        "content": "Rate limit: 100 requests per minute\n",
        "sha": "abc",
        "html_url": "https://example.com",
    }
    pr_context = "Title: Increase rate limit to 200/min\nAuthor: alice"

    result = await detector._score_doc(pr_context, doc, threshold=0.5)

    assert result is not None
    assert result["confidence"] == 0.92
    assert result["needs_update"] is True


@pytest.mark.asyncio
async def test_score_doc_below_threshold_returns_none(
    mock_claude, mock_github, mock_notion, mock_settings
):
    scoring_response = json.dumps({
        "needs_update": True,
        "confidence": 0.3,
        "change_type": "modify",
        "section_identifier": "some section",
        "evidence": {"event_signals": [], "doc_issues": [], "reasoning": "weak signal"},
        "original_section": "some text",
        "suggested_content": "new text",
    })
    mock_claude.generate = AsyncMock(return_value=scoring_response)

    detector = ChangeDetector(mock_claude, mock_github, mock_notion, mock_settings)
    doc = {
        "path": "docs/unrelated.md",
        "content": "Some unrelated content\n",
        "sha": "def",
        "html_url": "https://example.com",
    }
    pr_context = "Title: Fix typo\nAuthor: bob"

    result = await detector._score_doc(pr_context, doc, threshold=0.5)
    assert result is None


@pytest.mark.asyncio
async def test_score_doc_needs_update_false_returns_none(
    mock_claude, mock_github, mock_notion, mock_settings
):
    scoring_response = json.dumps({
        "needs_update": False,
        "confidence": 0.0,
    })
    mock_claude.generate = AsyncMock(return_value=scoring_response)

    detector = ChangeDetector(mock_claude, mock_github, mock_notion, mock_settings)
    doc = {
        "path": "docs/other.md",
        "content": "Unrelated content\n",
        "sha": "ghi",
        "html_url": "https://example.com",
    }

    result = await detector._score_doc("PR context", doc, threshold=0.5)
    assert result is None
