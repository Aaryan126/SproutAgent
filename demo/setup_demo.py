"""
Pre-hackathon demo setup script.

Run once before the demo to:
1. Create/update demo docs in the GitHub repo
2. Create draft PRs for the live demo

Usage:
    python demo/setup_demo.py
"""

import os

from dotenv import load_dotenv
from github import Github, GithubException

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")

API_DOCS_CONTENT = """# API Documentation

## Authentication

All API requests require an API key passed via the `Authorization` header.

Rate limit: 100 requests per minute

## Endpoints

### GET /api/v2/users

Fetch a list of users. Requires `users:read` scope.

**Response:**
```json
{
  "users": [...],
  "total": 42
}
```

### POST /api/v2/users

Create a new user. Requires `users:write` scope.

## Error Codes

| Code | Meaning |
|------|---------|
| 401  | Invalid or missing API key |
| 429  | Rate limit exceeded |
| 500  | Internal server error |
"""

README_CONTENT = """# Product Documentation

Welcome to the product docs!

## Features

- User management
- API access with rate limiting
- Analytics dashboard
- Webhook support

## Quick Start

1. Get your API key from the dashboard
2. Set the `Authorization: Bearer <key>` header
3. Call `GET /api/v2/users`

See [API Documentation](docs/api.md) for full reference.
"""


def ensure_file(repo, path: str, content: str, commit_message: str) -> None:
    try:
        existing = repo.get_contents(path)
        repo.update_file(
            path=path,
            message=commit_message,
            content=content,
            sha=existing.sha,
        )
        print(f"  Updated {path}")
    except GithubException:
        repo.create_file(
            path=path,
            message=commit_message,
            content=content,
        )
        print(f"  Created {path}")


RATE_LIMITER_CONTENT = """# Rate Limiter Configuration

MAX_REQUESTS_PER_MINUTE = 200
RATE_LIMIT_HEADERS_ENABLED = True
"""


def create_rate_limit_pr(repo) -> str:
    branch = "demo/increase-rate-limit"
    main_sha = repo.get_branch("main").commit.sha

    try:
        repo.create_git_ref(ref=f"refs/heads/{branch}", sha=main_sha)
        print(f"  Created branch {branch}")
    except GithubException:
        print(f"  Branch {branch} already exists")

    # Add a commit to the branch so GitHub allows PR creation
    try:
        existing = repo.get_contents("src/rate_limiter.py", ref=branch)
        repo.update_file(
            path="src/rate_limiter.py",
            message="feat: increase rate limit to 200 requests/min",
            content=RATE_LIMITER_CONTENT,
            sha=existing.sha,
            branch=branch,
        )
    except GithubException:
        repo.create_file(
            path="src/rate_limiter.py",
            message="feat: increase rate limit to 200 requests/min",
            content=RATE_LIMITER_CONTENT,
            branch=branch,
        )
    print("  Added rate_limiter.py commit to branch")

    pr_body = """## Changes

- Updated rate limiter configuration
- Increased limit from 100 to 200 requests/min
- Added `X-RateLimit-Remaining` header to all responses

## Testing

- Load tested at 250 req/min with no errors
- Confirmed `429` responses at 201 req/min

## Why

Customer request: current 100/min limit is blocking high-volume integrations.
"""

    try:
        pr = repo.create_pull(
            title="Increase API rate limit to 200/min",
            body=pr_body,
            head=branch,
            base="main",
            draft=True,
        )
        print(f"  Created draft PR #{pr.number}: {pr.html_url}")
        return pr.html_url
    except GithubException as e:
        print(f"  PR may already exist: {e}")
        return ""


def main() -> None:
    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("ERROR: Set GITHUB_TOKEN and GITHUB_REPO in .env")
        return

    gh = Github(GITHUB_TOKEN)
    repo = gh.get_repo(GITHUB_REPO)
    print(f"Connected to repo: {repo.full_name}")

    print("\n1. Setting up demo documentation...")
    ensure_file(repo, "docs/api.md", API_DOCS_CONTENT, "docs: Add API documentation for demo")
    ensure_file(repo, "README.md", README_CONTENT, "docs: Add README for demo")

    print("\n2. Creating demo PRs...")
    pr_url = create_rate_limit_pr(repo)

    print("\n✅ Demo environment ready!")
    print("\nDemo day checklist:")
    print("  1. Start server:  uvicorn app.main:app --reload --port 8000")
    print("  2. Start ngrok:   ngrok http 8000")
    print("  3. Set GitHub webhook URL to:  https://<ngrok-id>.ngrok.io/webhook/github")
    print("  4. Set webhook secret to match GITHUB_WEBHOOK_SECRET in .env")
    print("  5. Subscribe to: pull_request events")
    if pr_url:
        print(f"\n  DEMO PR (do NOT merge until demo):  {pr_url}")
    print("\n  During demo: merge the PR above, then watch the agent create a doc update PR!")


if __name__ == "__main__":
    main()
