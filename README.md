# Sprout Agent — AI Documentation Agent

An event-driven AI agent that watches GitHub PRs, detects when documentation becomes stale, generates surgical edits with confidence scores, and routes them to the right human for approval via Slack or a web dashboard.

**Core philosophy: don't make humans write docs, make them say yes or no.**

Live deployment: **`https://app-production-fd7d.up.railway.app`**

---

## How It Works

1. A PR is merged in your GitHub repo
2. GitHub sends a webhook to the agent
3. Claude extracts entities from the PR (API values, config changes, feature names)
4. The agent searches GitHub markdown docs AND Notion pages for those entities
5. Claude scores each doc (0–1 confidence) and generates a surgical edit
6. If confidence > 0.5, the agent opens a GitHub PR for markdown docs and queues a Notion page edit
7. The PR author gets a Slack message with Approve/Reject buttons
8. One click — GitHub PR is merged and/or Notion page is updated automatically

---

## Integrations

| Integration | What it does |
|-------------|-------------|
| **GitHub** | Webhook ingestion, signature validation, doc search, PR creation, auto-merge on approval |
| **Notion** | Fetches all accessible pages, scores them with Claude, applies surgical block-level edits on approval |
| **Slack** | Posts doc update notifications with Approve/Reject buttons; one click records the decision and triggers the update |
| **Claude (Sonnet)** | Change detection, confidence scoring with evidence, surgical edit generation, prompt caching |

---

## Tech Stack

- **Framework:** FastAPI (Python 3.11)
- **AI:** Anthropic Claude (`claude-sonnet-4-6`) with prompt caching
- **Database:** SQLite via SQLAlchemy async
- **GitHub:** PyGithub
- **Notion:** notion-client (AsyncClient)
- **Slack:** slack-sdk (AsyncWebClient)
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
    github_api.py          # GitHubClient — search docs, create PRs, merge PRs
    notion_api.py          # NotionClient — list pages, read blocks, apply surgical edits
    slack_api.py           # SlackClient — post notifications with Approve/Reject buttons
  agents/
    claude_client.py       # ClaudeClient wrapper with prompt caching + JSON parsing
    change_detector.py     # Entity extraction + doc search (GitHub + Notion) + confidence scoring
    update_generator.py    # Surgical edit generation + diff + PR body
    approver_router.py     # Route to PR author, CODEOWNERS, or default
  routers/
    webhooks.py            # POST /webhook/github — entry point for all events
    approvals.py           # GET/POST /approvals — review queue API
    dashboard.py           # GET /dashboard — status summary
    slack.py               # POST /slack/interactivity — Slack button callback handler
  utils/
    signature_validator.py # HMAC-SHA256 webhook signature validation
    diff_generator.py      # Unified diff generation + section replacement
  static/
    index.html             # Web dashboard — approval UI with diffs, evidence, confidence rings
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

**`doc_updates` statuses:** `pending` → `approved` → `applied` or `rejected`

**`doc_platform` values:** `github`, `notion`

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
| `NOTION_TOKEN` | No | Notion internal integration token (`secret_...`) |
| `SLACK_BOT_TOKEN` | No | Slack bot OAuth token (`xoxb-...`) |
| `SLACK_SIGNING_SECRET` | No | Slack app signing secret for request verification |
| `SLACK_CHANNEL` | No | Slack channel to post notifications (e.g. `#docs-updates`) |
| `DATABASE_URL` | No | Defaults to `sqlite+aiosqlite:///./docs_agent.db` |
| `DEFAULT_APPROVER` | Yes | GitHub username to assign PRs when no other approver found |
| `CONFIDENCE_THRESHOLD` | No | Minimum confidence to trigger a doc update (default: `0.5`) |
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
# Optionally add NOTION_TOKEN, SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET, SLACK_CHANNEL

# 3. Start server
uvicorn app.main:app --reload --port 8000

# 4. Expose via ngrok (new terminal)
ngrok http 8000
# Set webhook URL in GitHub to: https://<id>.ngrok-free.app/webhook/github
```

Open `http://localhost:8000` to see the dashboard.

---

## Notion Setup

1. Go to `notion.so/profile/integrations` and create a new internal connection
2. Enable Read, Update, and Insert content capabilities
3. Copy the access token as `NOTION_TOKEN`
4. On each Notion page you want the agent to watch: click `...` > "Connect to" > select your integration

The agent fetches all pages the integration has access to and scores them with Claude on every PR event.

---

## Slack Setup

1. Go to `api.slack.com/apps` and create a new app
2. Under "OAuth & Permissions", add bot scopes: `chat:write`, `chat:write.public`
3. Install to workspace and copy the Bot OAuth Token as `SLACK_BOT_TOKEN`
4. Copy the Signing Secret as `SLACK_SIGNING_SECRET`
5. Under "Interactivity & Shortcuts", enable interactivity and set the Request URL to:
   `https://your-domain.up.railway.app/slack/interactivity`
6. Invite the bot to your chosen channel with `/invite @YourBotName`

---

## Demo Setup

Run once before the demo to populate the target repo with sample docs and a ready-to-merge PR:

```bash
python demo/setup_demo.py
```

This creates:
- `docs/api.md` with "Rate limit: 100 requests per minute"
- A branch with `MAX_REQUESTS_PER_MINUTE = 2750`
- A draft PR titled "Increase API rate limit to 2750/min"

**Demo flow:** merge the PR, agent detects the mismatch in both GitHub docs and Notion, Slack message arrives with Approve/Reject buttons, one click updates everything.

---

## Running Tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

Tests cover:
- Webhook signature validation (security-critical)
- Webhook endpoint behavior (valid, invalid, ignored, duplicate)
- Claude JSON parsing (fence stripping, malformed responses)
- Change detection (entity extraction, confidence scoring)
- Diff generation and section replacement

---

## Deployment (Railway)

```bash
# Deploy
railway up

# View logs
railway logs

# Set environment variables
railway variables set KEY="value"
```

### GitHub Webhook Configuration

- **Payload URL:** `https://app-production-fd7d.up.railway.app/webhook/github`
- **Content type:** `application/json`
- **Events:** Pull requests

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness check |
| `GET` | `/` | Redirects to dashboard UI |
| `POST` | `/webhook/github` | Receives GitHub PR merge events |
| `GET` | `/approvals/` | List all doc update proposals |
| `GET` | `/approvals/{id}` | Get a single proposal |
| `POST` | `/approvals/{id}/decide` | Record approval or rejection |
| `GET` | `/dashboard/` | Summary counts and recent updates |
| `POST` | `/slack/interactivity` | Handles Slack Approve/Reject button clicks |

---

## Key Design Decisions

- **Surgical edits only.** Claude modifies only the affected sentence or paragraph. Full rewrites are a bug.
- **Human always approves.** No auto-merge path without a human decision, even at confidence 1.0.
- **Multi-platform targets.** GitHub markdown docs and Notion pages are both first-class targets.
- **Slack as the approval surface.** Approvers get a Slack ping with buttons — no need to open a dashboard.
- **Notion uses block-level matching.** When the original section spans multiple blocks, the agent diffs line by line and updates only the blocks that changed.
- **SQLite for MVP.** Swap to Postgres via `DATABASE_URL` without code changes.
- **Confidence threshold is configurable.** Set via `config` DB table or `CONFIDENCE_THRESHOLD` env var.
- **Webhook deduplication.** GitHub delivers webhooks multiple times. Deduplicated by `X-GitHub-Delivery` header.

---

## What's Next

- Learning from approvals to improve confidence scoring over time
- Auto-approve at very high confidence for low-risk changes
- Linear and Jira as additional event sources
- Slack as a doc source (decisions made in Slack trigger doc updates)
- Multi-doc updates (one PR triggers updates across multiple files and pages)
