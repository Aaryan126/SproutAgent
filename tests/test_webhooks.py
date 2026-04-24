import hashlib
import hmac
import json
import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401 — registers all ORM models with Base.metadata
from app.database import Base, get_db
from app.utils.signature_validator import validate_github_signature

TEST_SECRET = "test-webhook-secret"
TEST_DB_URL = "sqlite+aiosqlite:///./test_docs_agent.db"


def make_signature(body: bytes, secret: str = TEST_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def load_fixture(name: str) -> dict:
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", name)
    with open(fixture_path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Unit tests: validate_github_signature
# ---------------------------------------------------------------------------

def test_valid_signature():
    body = b'{"action": "closed"}'
    sig = make_signature(body)
    assert validate_github_signature(body, sig, TEST_SECRET) is True


def test_invalid_signature_wrong_secret():
    body = b'{"action": "closed"}'
    sig = make_signature(body, secret="wrong-secret")
    assert validate_github_signature(body, sig, TEST_SECRET) is False


def test_missing_signature_header():
    with pytest.raises(ValueError, match="Missing"):
        validate_github_signature(b"body", None, TEST_SECRET)


def test_malformed_signature_no_prefix():
    with pytest.raises(ValueError, match="Invalid signature format"):
        validate_github_signature(b"body", "abc123", TEST_SECRET)


# ---------------------------------------------------------------------------
# Integration tests: webhook endpoint
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
async def test_db():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    yield override_get_db

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if os.path.exists("./test_docs_agent.db"):
        os.remove("./test_docs_agent.db")


@pytest.fixture(scope="function")
async def client(test_db, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", TEST_SECRET)
    monkeypatch.setenv("GITHUB_REPO", "owner/repo")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    monkeypatch.setenv("DEFAULT_APPROVER", "admin")

    from app.main import app
    from app.routers import webhooks

    app.dependency_overrides[get_db] = test_db

    original_add_task = None

    def mock_add_task(func, *args, **kwargs):
        pass

    import unittest.mock as mock
    with mock.patch("fastapi.BackgroundTasks.add_task", mock_add_task):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_webhook_accepts_merged_pr(client):
    payload = load_fixture("sample_pr_event.json")
    body = json.dumps(payload).encode()
    sig = make_signature(body)

    response = await client.post(
        "/webhook/github",
        content=body,
        headers={
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "test-delivery-001",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"


@pytest.mark.asyncio
async def test_webhook_rejects_bad_signature(client):
    payload = load_fixture("sample_pr_event.json")
    body = json.dumps(payload).encode()

    response = await client.post(
        "/webhook/github",
        content=body,
        headers={
            "X-Hub-Signature-256": "sha256=badhash",
            "X-GitHub-Event": "pull_request",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_ignores_non_merged_pr(client):
    payload = load_fixture("sample_pr_event.json")
    payload["pull_request"]["merged"] = False
    body = json.dumps(payload).encode()
    sig = make_signature(body)

    response = await client.post(
        "/webhook/github",
        content=body,
        headers={
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": "pull_request",
            "X-GitHub-Delivery": "test-delivery-002",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


@pytest.mark.asyncio
async def test_webhook_deduplicates(client):
    payload = load_fixture("sample_pr_event.json")
    body = json.dumps(payload).encode()
    sig = make_signature(body)
    headers = {
        "X-Hub-Signature-256": sig,
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": "test-delivery-dup-001",
        "Content-Type": "application/json",
    }

    resp1 = await client.post("/webhook/github", content=body, headers=headers)
    assert resp1.json()["status"] == "received"

    resp2 = await client.post("/webhook/github", content=body, headers=headers)
    assert resp2.json()["status"] == "duplicate"


@pytest.mark.asyncio
async def test_webhook_ignores_non_pr_event(client):
    body = json.dumps({"action": "published", "release": {}}).encode()
    sig = make_signature(body)

    response = await client.post(
        "/webhook/github",
        content=body,
        headers={
            "X-Hub-Signature-256": sig,
            "X-GitHub-Event": "release",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
