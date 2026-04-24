# Sprout Agent — AI Documentation Agent

An event-driven AI agent that watches GitHub PRs, detects when documentation becomes stale, generates surgical edits with confidence scores, and creates GitHub PRs for human approval.

**Core philosophy: don't make humans write docs, make them say yes or no.**

---

## How It Works

1. A PR is merged in your target GitHub repo
2. GitHub sends a webhook to the agent
3. Claude extracts entities from the PR (API values, config changes, feature names)
4. The agent searches your repo's markdown docs for those entities
5. Claude scores each doc (0-1 confidence) and generates a surgical edit
6. If confidence > 0.5, the agent opens a GitHub PR with the proposed change
7. The PR author reviews and approves or rejects

---

## Tech Stack

- **Framework:** FastAPI (Python 3.11)
- **AI:** Anthropic Claude (`claude-sonnet-4-6`) with prompt caching
- **Database:** SQLite via SQLAlchemy async
- **GitHub:** PyGithub
- **Logging:** structlog (JSON)
- **Config:** pydantic-settings
- **Deployment:** Railway (Docker)
- **Testing:** pytest + pytest-asyncio + httpx

---

## Project Structure

```
app/
  main.py                  # FastAPI entry point, lifespan, router registration
  config.py                # All env var config via pydantic-settings
  database.py              # Async SQLAlchemy engine, session factory, Base
  models/
    event.py               # Event ORM model (incoming webhooks)
    doc_update.py          # DocUpdate ORM model (proposed changes)
    approval.py            # Approval + Config ORM models
  integrations/
    github_api.py          # GitHubClient — search docs, create PRs
    notion_api.py          # NotionClient — stub (phase 2)
  agents/
    claude_client.py       # ClaudeClient wrapper with prompt caching + JSON parsing
    change_detector.py     # Entity extraction + doc search + confidence scoring
    update_generator.py    # Surgical edit generation + diff + PR body
    approver_router.py     # Route to PR author, CODEOWNERS, or default
  routers/
    webhooks.py            # POST /webhook/github — entry point for all events
    approvals.py           # GET/POST /approvals — review queue
    dashboard.py           # GET /dashboard — status summary
  utils/
    signature_validator.py # HMAC-SHA256 webhook signature validation
    diff_generator.py      # Unified diff generation + section replacement
tests/
  fixtures/
    sample_pr_event.json   # Sample GitHub PR webhook payload
  test_webhooks.py         # Signature validation + webhook endpoint tests
  test_change_detection.py # Entity extraction + confidence scoring tests
demo/
  setup_demo.py            # Creates demo docs + draft PRs in target repo
  demo_script.md           # Cue card for live demo presentation
Dockerfile
docker-compose.yml
requirements.txt
.env.example
pyproject.toml
```

---

## Database Schema

| Table | Purpose |
|-------|---------|
| `events` | Incoming webhook events from GitHub |
| `doc_updates` | Proposed documentation changes with confidence scores |
| `approvals` | Human approval/rejection decisions |
| `config` | Runtime configuration (e.g. confidence threshold) |

**`doc_updates` statuses:** `pending`, `approved`, `rejected`, `applied`

**Change types:** `add`, `modify`, `remove`, `deprecate`

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | Yes | Personal access token with `repo` scope |
| `GITHUB_WEBHOOK_SECRET` | Yes | Shared secret for HMAC signature validation |
| `GITHUB_REPO` | Yes | Target repo to watch and search (e.g. `owner/repo`) |
| `GITHUB_DOCS_REPO` | No | Separate docs repo — leave blank to use `GITHUB_REPO` |
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |
| `DATABASE_URL` | No | Defaults to `sqlite+aiosqlite:///./docs_agent.db` |
| `DEFAULT_APPROVER` | Yes | GitHub username to assign PRs when no other approver found |
| `CONFIDENCE_THRESHOLD` | No | Minimum confidence to trigger a doc PR (default: `0.5`) |
| `ENVIRONMENT` | No | `development` or `production` |
| `LOG_LEVEL` | No | `INFO` or `DEBUG` |

---

## Local Development

```bash
# 1. Clone and set up
git clone https://github.com/Aaryan126/SproutAgent
cd SproutAgent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Fill in GITHUB_TOKEN, GITHUB_WEBHOOK_SECRET, GITHUB_REPO,
# ANTHROPIC_API_KEY, DEFAULT_APPROVER

# 3. Start server
uvicorn app.main:app --reload --port 8000

# 4. Expose via ngrok (new terminal)
ngrok http 8000
# Set webhook URL in GitHub to: https://<id>.ngrok-free.app/webhook/github
```

---

## Demo Setup

Run once before the demo to populate the target repo with sample docs and a ready-to-merge PR:

```bash
python demo/setup_demo.py
```

This creates:
- `docs/api.md` with "Rate limit: 100 requests per minute"
- `src/rate_limiter.py` on a branch with `MAX_REQUESTS_PER_MINUTE = 200`
- A draft PR titled "Increase API rate limit to 200/min"

**Demo flow:** merge the PR, watch the agent detect the mismatch, create a doc update PR changing `100` to `200`.

---

## Running Tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

22 tests covering:
- Webhook signature validation (security-critical)
- Webhook endpoint behavior (valid, invalid, ignored, duplicate)
- Claude JSON parsing (fence stripping, malformed responses)
- Change detection (entity extraction, confidence scoring)
- Diff generation and section replacement

---

## Deployment (Railway)

The agent is deployed on Railway at:
**`https://app-production-fd7d.up.railway.app`**

### To redeploy after code changes:

```bash
railway up
```

### To view live logs:

```bash
railway logs
```

### To update environment variables:

```bash
railway variables set KEY="value"
```

### GitHub Webhook Configuration

The GitHub webhook on `Sprout-Demo` is set to:
- **Payload URL:** `https://app-production-fd7d.up.railway.app/webhook/github`
- **Content type:** `application/json`
- **Events:** Pull requests

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check |
| `POST` | `/webhook/github` | Receives GitHub PR events |
| `GET` | `/approvals/` | List all doc update proposals |
| `GET` | `/approvals/{id}` | Get a single proposal |
| `POST` | `/approvals/{id}/decide` | Record approval or rejection |
| `GET` | `/dashboard/` | Summary counts and recent updates |

---

## Key Design Decisions

- **Surgical edits only.** Claude modifies the affected sentence/paragraph only. Full rewrites are a bug.
- **Human always approves.** No auto-merge path, even at confidence 1.0.
- **GitHub-first.** Notion/Slack are phase 2.
- **SQLite for MVP.** Swap to Postgres via `DATABASE_URL` without code changes.
- **Confidence threshold is configurable.** Set via `config` DB table or `CONFIDENCE_THRESHOLD` env var.
- **Webhook deduplication.** GitHub delivers webhooks multiple times. We deduplicate by `X-GitHub-Delivery` header.

---

## Phase 2 (Not Yet Implemented)

- Notion integration (`app/integrations/notion_api.py` is stubbed)
- Slack notifications
- Dashboard UI
- Learning from approvals to improve confidence scoring
- Auto-approve at very high confidence thresholds
