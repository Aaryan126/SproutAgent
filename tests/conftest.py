import os

# Set required env vars before any app module is imported.
# These are test-only values — no real tokens.
os.environ.setdefault("GITHUB_TOKEN", "test-token")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("GITHUB_REPO", "owner/repo")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-api-key")
os.environ.setdefault("DEFAULT_APPROVER", "test-admin")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_docs_agent.db")
