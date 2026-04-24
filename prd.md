# PRD.md - AI Documentation Agent

# PRD.md - AI Documentation Agent

**Version:** 1.0 (Hackathon MVP)  
**Last Updated:** 2024-04-24  
**Status:** Ready for Implementation  
**Target:** 1-day hackathon build  

---

## 🎯 Executive Summary

### What We're Building
An AI agent that watches where work happens (GitHub PRs, Linear tickets, Slack discussions), detects when documentation becomes outdated, drafts surgical updates with evidence, and routes them to the right person for approval—all automatically.

### The Problem
- Documentation goes stale because updating it feels like homework
- By the time someone notices, docs are months out of date
- Engineers know code changed but don't remember to update docs
- Sales/support teams use outdated information

### The Solution
**Don't make humans write docs. Make them say yes or no.**

The agent:
1. Watches GitHub PRs, Linear tickets, Slack messages
2. Detects specific events that should trigger doc updates
3. Drafts surgical edits (not rewrites) with confidence scores
4. Creates GitHub PRs or Notion updates for human approval
5. Routes to the person who knows best (PR author, doc owner)

---

## 🏗️ System Architecture

### High-Level Flow
```
┌─────────────────────────────────────────────┐
│         Work Platforms (Sources)             │
│  [GitHub PRs] [Linear Tickets] [Slack]      │
└───────────────┬─────────────────────────────┘
                │ webhooks
                ↓
┌─────────────────────────────────────────────┐
│         Event Processor (FastAPI)            │
│  • Receives webhooks                         │
│  • Validates signatures                      │
│  • Stores events                             │
└───────────────┬─────────────────────────────┘
                │
                ↓
┌─────────────────────────────────────────────┐
│      Change Detection Engine (Claude)        │
│  • Classify change type                      │
│  • Search affected docs                      │
│  • Calculate confidence                      │
│  • Generate surgical edits                   │
└───────────────┬─────────────────────────────┘
                │
                ↓
┌─────────────────────────────────────────────┐
│       Approval Orchestrator                  │
│  • Route to right approver                   │
│  • Create GitHub PR (dev docs)               │
│  • Create Notion update (other docs)         │
│  • Track approval status                     │
└───────────────┬─────────────────────────────┘
                │
                ↓
┌─────────────────────────────────────────────┐
│     Documentation Platforms (Targets)        │
│  [GitHub Repo Docs] [Notion Wiki]           │
└─────────────────────────────────────────────┘
```

---

## 🔧 Technical Stack

### Backend
- **Framework:** FastAPI (Python 3.11+)
- **Database:** SQLite (MVP) → PostgreSQL (production)
- **AI:** Anthropic Claude 3.5 Sonnet
- **Task Queue:** Background tasks (asyncio) → Celery (production)
- **Logging:** structlog

### Integrations
- **GitHub:** PyGithub + webhooks
- **Notion:** notion-client (official SDK)
- **Linear:** GraphQL API (optional, phase 2)
- **Slack:** slack-sdk (optional, phase 2)

### Development
- **Local Server:** uvicorn
- **Tunneling:** ngrok (local) → stable URL (production)
- **Testing:** pytest + httpx
- **Linting:** ruff

### Deployment-Ready Architecture
- Use environment variables for all config
- Docker support (Dockerfile included)
- Health check endpoints
- Structured logging for debugging

---

## 📁 Project Structure

```
docs-agent/
├── README.md
├── PRD.md (this file)
├── requirements.txt
├── .env.example
├── Dockerfile (deployment-ready)
├── docker-compose.yml
│
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app entry
│   ├── config.py                  # Environment config
│   ├── database.py                # SQLite/Postgres setup
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── event.py               # Event data models
│   │   ├── doc_update.py          # Update proposal models
│   │   └── approval.py            # Approval tracking models
│   │
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── github_webhook.py      # GitHub webhook handler
│   │   ├── github_api.py          # GitHub API client
│   │   ├── notion_api.py          # Notion API client
│   │   ├── linear_api.py          # Linear (future)
│   │   └── slack_api.py           # Slack (future)
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── claude_client.py       # Claude API wrapper
│   │   ├── change_detector.py     # Event → doc mapping
│   │   ├── update_generator.py    # Generate surgical edits
│   │   ├── confidence_scorer.py   # Calculate confidence
│   │   └── approver_router.py     # Route to right person
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── webhooks.py            # Webhook endpoints
│   │   ├── approvals.py           # Approval endpoints
│   │   └── dashboard.py           # Status dashboard (optional)
│   │
│   └── utils/
│       ├── __init__.py
│       ├── diff_generator.py      # Create markdown diffs
│       ├── entity_extractor.py    # Extract entities from text
│       └── signature_validator.py # Webhook signature validation
│
├── tests/
│   ├── __init__.py
│   ├── test_webhooks.py
│   ├── test_change_detection.py
│   └── fixtures/
│       ├── sample_pr_event.json
│       └── sample_docs.md
│
└── demo/
    ├── setup_demo.py              # Create demo repo/docs
    ├── sample_prs.json            # PRs to merge during demo
    └── demo_script.md             # What to say during demo
```

---

## 🗄️ Database Schema

### SQLite Schema (MVP)

```sql
-- Events from work platforms
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,              -- 'github', 'linear', 'slack'
    event_type TEXT NOT NULL,          -- 'pr_merged', 'ticket_closed', etc.
    event_id TEXT UNIQUE NOT NULL,     -- External ID
    raw_payload JSON NOT NULL,
    entities JSON,                     -- Extracted entities
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    
    INDEX idx_source (source),
    INDEX idx_event_type (event_type),
    INDEX idx_created (created_at)
);

-- Documentation update proposals
CREATE TABLE doc_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    doc_platform TEXT NOT NULL,        -- 'github', 'notion'
    doc_path TEXT NOT NULL,            -- File path or Notion page ID
    doc_section TEXT,                  -- Specific section/line
    
    change_type TEXT NOT NULL,         -- 'add', 'modify', 'remove', 'deprecate'
    original_content TEXT,
    proposed_content TEXT NOT NULL,
    diff_markdown TEXT NOT NULL,       -- Formatted diff
    
    confidence_score REAL NOT NULL,    -- 0.0 to 1.0
    evidence JSON NOT NULL,            -- Why this update is needed
    
    status TEXT DEFAULT 'pending',     -- 'pending', 'approved', 'rejected', 'applied'
    assigned_to TEXT,                  -- GitHub username
    
    github_pr_url TEXT,                -- If using PR workflow
    notion_page_url TEXT,              -- If updating Notion
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP,
    applied_at TIMESTAMP,
    
    FOREIGN KEY (event_id) REFERENCES events(id),
    INDEX idx_status (status),
    INDEX idx_assigned (assigned_to)
);

-- Approval decisions
CREATE TABLE approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_update_id INTEGER NOT NULL,
    approver TEXT NOT NULL,            -- GitHub username
    decision TEXT NOT NULL,            -- 'approved', 'rejected', 'edited'
    comment TEXT,
    decided_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (doc_update_id) REFERENCES doc_updates(id)
);

-- Configuration (doc paths, approvers, rules)
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value JSON NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🔌 Integration Details

### 1. GitHub Integration

#### Setup Requirements
1. Create GitHub App or Personal Access Token
2. Required permissions:
   - Repository: Read & Write (for PRs)
   - Contents: Read & Write (for docs)
   - Pull Requests: Read & Write
   - Webhooks: Read & Write
3. Subscribe to webhook events:
   - `pull_request` (closed, merged)
   - `issues` (closed)
   - `release` (published)

#### Webhook Endpoint
```python
# app/routers/webhooks.py

from fastapi import APIRouter, Request, HTTPException, Header
import hmac
import hashlib

router = APIRouter(prefix="/webhook")

@router.post("/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None)
):
    """
    Receives GitHub webhook events.
    
    Security:
    - Validates HMAC signature
    - Verifies GitHub headers
    
    Supported Events:
    - pull_request (action: closed, merged: true)
    - issues (action: closed)
    - release (action: published)
    """
    # Get raw body for signature verification
    body = await request.body()
    
    # Verify signature
    if not verify_github_signature(body, x_hub_signature_256):
        raise HTTPException(401, "Invalid signature")
    
    # Parse payload
    payload = await request.json()
    
    # Store event
    event = await store_event(
        source="github",
        event_type=x_github_event,
        event_id=payload.get("id"),
        raw_payload=payload
    )
    
    # Process async (don't block webhook)
    background_tasks.add_task(process_event, event.id)
    
    return {"status": "received", "event_id": event.id}

def verify_github_signature(body: bytes, signature: str) -> bool:
    """Verify GitHub webhook signature."""
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    expected = "sha256=" + hmac.new(
        secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

#### GitHub API Client
```python
# app/integrations/github_api.py

from github import Github
from typing import List, Optional

class GitHubClient:
    def __init__(self, token: str):
        self.client = Github(token)
    
    def get_pr(self, repo: str, pr_number: int):
        """Fetch PR details."""
        repo_obj = self.client.get_repo(repo)
        return repo_obj.get_pull(pr_number)
    
    def search_docs(self, repo: str, query: str) -> List[dict]:
        """
        Search documentation files for a query.
        
        Returns list of:
        - path: file path
        - content: file content
        - url: GitHub URL
        """
        repo_obj = self.client.get_repo(repo)
        
        # Search in common doc locations
        doc_paths = [
            "docs/",
            "README.md",
            "CHANGELOG.md",
            "*.md"
        ]
        
        results = []
        contents = repo_obj.get_contents("")
        
        for content in contents:
            if content.type == "dir" and content.path in ["docs", "documentation"]:
                # Recursively search docs directory
                results.extend(self._search_directory(repo_obj, content.path, query))
            elif content.path.endswith(".md"):
                # Check markdown files in root
                file_content = content.decoded_content.decode()
                if query.lower() in file_content.lower():
                    results.append({
                        "path": content.path,
                        "content": file_content,
                        "url": content.html_url,
                        "sha": content.sha
                    })
        
        return results
    
    def create_doc_update_pr(
        self,
        repo: str,
        file_path: str,
        new_content: str,
        branch_name: str,
        title: str,
        body: str,
        assignee: str
    ) -> str:
        """
        Create a PR with documentation update.
        
        Returns: PR URL
        """
        repo_obj = self.client.get_repo(repo)
        
        # Get default branch
        default_branch = repo_obj.default_branch
        base_ref = repo_obj.get_git_ref(f"heads/{default_branch}")
        
        # Create new branch
        repo_obj.create_git_ref(
            ref=f"refs/heads/{branch_name}",
            sha=base_ref.object.sha
        )
        
        # Update file
        file = repo_obj.get_contents(file_path, ref=default_branch)
        repo_obj.update_file(
            path=file_path,
            message=f"docs: {title}",
            content=new_content,
            sha=file.sha,
            branch=branch_name
        )
        
        # Create PR
        pr = repo_obj.create_pull(
            title=f"🤖 [Docs] {title}",
            body=body,
            head=branch_name,
            base=default_branch
        )
        
        # Assign to reviewer
        pr.create_review_request(reviewers=[assignee])
        
        # Add labels
        pr.add_to_labels("documentation", "automated")
        
        return pr.html_url
```

---

### 2. Notion Integration

#### Setup Requirements
1. Create Notion integration at https://www.notion.so/my-integrations
2. Get integration token
3. Share relevant pages/databases with the integration
4. Required capabilities:
   - Read content
   - Update content
   - Insert content

#### Notion API Client
```python
# app/integrations/notion_api.py

from notion_client import Client
from typing import List, Dict, Optional

class NotionClient:
    def __init__(self, token: str):
        self.client = Client(auth=token)
    
    def search_pages(self, query: str) -> List[Dict]:
        """
        Search Notion pages for content.
        
        Returns list of matching pages with:
        - id: page ID
        - title: page title
        - url: Notion URL
        - last_edited: timestamp
        """
        results = self.client.search(
            query=query,
            filter={"property": "object", "value": "page"}
        )
        
        return [
            {
                "id": page["id"],
                "title": self._get_title(page),
                "url": page["url"],
                "last_edited": page["last_edited_time"]
            }
            for page in results["results"]
        ]
    
    def get_page_content(self, page_id: str) -> str:
        """
        Get full content of a Notion page as markdown-like text.
        """
        blocks = self.client.blocks.children.list(page_id)
        content = []
        
        for block in blocks["results"]:
            content.append(self._block_to_text(block))
        
        return "\n".join(content)
    
    def update_block(
        self,
        block_id: str,
        new_content: str,
        block_type: str = "paragraph"
    ):
        """
        Update a specific block in a Notion page.
        
        For surgical edits - update only the affected block.
        """
        self.client.blocks.update(
            block_id=block_id,
            **{
                block_type: {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": new_content}
                        }
                    ]
                }
            }
        )
    
    def append_block(
        self,
        page_id: str,
        content: str,
        block_type: str = "paragraph"
    ):
        """
        Append a new block to a page.
        """
        self.client.blocks.children.append(
            block_id=page_id,
            children=[
                {
                    "object": "block",
                    "type": block_type,
                    block_type: {
                        "rich_text": [
                            {
                                "type": "text",
                                "text": {"content": content}
                            }
                        ]
                    }
                }
            ]
        )
    
    def create_update_comment(
        self,
        page_id: str,
        message: str,
        mention_user: Optional[str] = None
    ):
        """
        Add a comment to a Notion page.
        Used to notify about proposed updates.
        """
        rich_text = [{"type": "text", "text": {"content": message}}]
        
        if mention_user:
            rich_text.insert(0, {
                "type": "mention",
                "mention": {"type": "user", "user": {"id": mention_user}}
            })
        
        self.client.comments.create(
            parent={"page_id": page_id},
            rich_text=rich_text
        )
    
    def _get_title(self, page: Dict) -> str:
        """Extract title from page object."""
        try:
            title_property = page["properties"].get("title", {})
            if title_property.get("title"):
                return title_property["title"][0]["plain_text"]
        except (KeyError, IndexError):
            pass
        return "Untitled"
    
    def _block_to_text(self, block: Dict) -> str:
        """Convert Notion block to plain text."""
        block_type = block["type"]
        
        if block_type in ["paragraph", "heading_1", "heading_2", "heading_3"]:
            rich_text = block[block_type].get("rich_text", [])
            return "".join([text["plain_text"] for text in rich_text])
        
        elif block_type == "bulleted_list_item":
            rich_text = block[block_type].get("rich_text", [])
            text = "".join([text["plain_text"] for text in rich_text])
            return f"• {text}"
        
        elif block_type == "code":
            rich_text = block[block_type].get("rich_text", [])
            code = "".join([text["plain_text"] for text in rich_text])
            language = block[block_type].get("language", "")
            return f"```{language}\n{code}\n```"
        
        return ""
```

---

## 🤖 AI Agent Implementation

### Change Detection Engine

```python
# app/agents/change_detector.py

from typing import List, Dict, Optional
from app.agents.claude_client import ClaudeClient
from app.integrations.github_api import GitHubClient
from app.integrations.notion_api import NotionClient

class ChangeDetector:
    """
    Analyzes events to determine if docs need updating.
    
    Key Principles:
    1. Event-driven (not staleness detection)
    2. Surgical identification (specific paragraphs, not whole docs)
    3. Confidence scoring (0.0 to 1.0)
    4. Evidence trail (why this update is needed)
    """
    
    def __init__(
        self,
        claude: ClaudeClient,
        github: GitHubClient,
        notion: NotionClient
    ):
        self.claude = claude
        self.github = github
        self.notion = notion
    
    async def analyze_event(self, event: Dict) -> List[Dict]:
        """
        Analyze an event and return proposed doc updates.
        
        Returns list of:
        - doc_platform: 'github' or 'notion'
        - doc_path: file path or page ID
        - doc_section: specific section/block
        - change_type: 'add', 'modify', 'remove', 'deprecate'
        - proposed_content: new content
        - confidence: 0.0 to 1.0
        - evidence: why update is needed
        """
        # Step 1: Extract entities from event
        entities = await self._extract_entities(event)
        
        # Step 2: Find potentially affected docs
        affected_docs = await self._find_affected_docs(entities)
        
        # Step 3: Analyze each doc to see if update needed
        updates = []
        for doc in affected_docs:
            update = await self._analyze_doc(event, entities, doc)
            if update and update["confidence"] > 0.5:  # Threshold
                updates.append(update)
        
        return updates
    
    async def _extract_entities(self, event: Dict) -> Dict:
        """
        Extract key entities from event that might appear in docs.
        
        Examples:
        - API endpoints: "/api/v2/users"
        - Feature names: "OAuth", "SSO"
        - Configuration values: "rate_limit: 200"
        - Technical terms: "authentication", "webhook"
        """
        prompt = f"""
Extract key entities from this event that might appear in documentation.

Event Type: {event['event_type']}
Source: {event['source']}

Event Details:
{self._format_event_for_claude(event)}

Extract:
1. API endpoints or URLs mentioned
2. Feature names or capabilities
3. Configuration values (numbers, limits, etc.)
4. Technical terms or concepts
5. Product names or integrations

Return as JSON:
{{
    "endpoints": [...],
    "features": [...],
    "config_values": [...],
    "terms": [...],
    "products": [...]
}}
"""
        
        response = await self.claude.generate(prompt)
        return self._parse_json(response)
    
    async def _find_affected_docs(self, entities: Dict) -> List[Dict]:
        """
        Search all doc platforms for docs mentioning these entities.
        """
        affected_docs = []
        
        # Search GitHub docs
        for entity_type, values in entities.items():
            for value in values:
                github_results = self.github.search_docs(
                    repo=os.getenv("GITHUB_REPO"),
                    query=value
                )
                
                for result in github_results:
                    affected_docs.append({
                        "platform": "github",
                        "path": result["path"],
                        "content": result["content"],
                        "url": result["url"],
                        "matched_entity": value,
                        "entity_type": entity_type
                    })
        
        # Search Notion docs
        for entity_type, values in entities.items():
            for value in values:
                notion_results = self.notion.search_pages(query=value)
                
                for result in notion_results:
                    content = self.notion.get_page_content(result["id"])
                    affected_docs.append({
                        "platform": "notion",
                        "path": result["id"],
                        "title": result["title"],
                        "content": content,
                        "url": result["url"],
                        "matched_entity": value,
                        "entity_type": entity_type
                    })
        
        return affected_docs
    
    async def _analyze_doc(
        self,
        event: Dict,
        entities: Dict,
        doc: Dict
    ) -> Optional[Dict]:
        """
        Analyze if this specific doc needs updating.
        
        Use Claude to:
        1. Determine if update is needed
        2. Calculate confidence score
        3. Identify specific section to update
        4. Generate evidence trail
        """
        prompt = f"""
You are analyzing whether a documentation file needs updating based on a recent event.

EVENT:
Type: {event['event_type']}
{self._format_event_for_claude(event)}

DOCUMENTATION:
Platform: {doc['platform']}
Path: {doc['path']}
Content:
```
{doc['content']}
```

TASK:
1. Does this doc need updating based on the event?
2. If yes, which specific section/paragraph needs updating?
3. What type of change is needed?
   - add: New information to add
   - modify: Existing info needs correction
   - remove: Outdated info to remove
   - deprecate: Mark something as deprecated

4. Calculate confidence score (0.0 to 1.0):
   - 0.9-1.0: Certain (explicit mention, clear mismatch)
   - 0.7-0.9: High (strongly implied, likely outdated)
   - 0.5-0.7: Medium (possibly outdated, worth reviewing)
   - <0.5: Low (unclear, might be fine)

5. Provide evidence trail:
   - What in the event suggests this update?
   - What in the doc is now outdated?
   - Why are you confident?

Return JSON:
{{
    "needs_update": true/false,
    "confidence": 0.85,
    "change_type": "modify",
    "section_identifier": "line 45" or "## Authentication section",
    "evidence": {{
        "event_signals": ["PR changed rate limit to 200"],
        "doc_issues": ["Doc still says 100 requests/min"],
        "reasoning": "Clear mismatch between code and docs"
    }},
    "suggested_content": "New content here..."
}}

If needs_update is false, return {{"needs_update": false}}
"""
        
        response = await self.claude.generate(prompt)
        analysis = self._parse_json(response)
        
        if not analysis.get("needs_update"):
            return None
        
        return {
            "doc_platform": doc["platform"],
            "doc_path": doc["path"],
            "doc_section": analysis["section_identifier"],
            "doc_url": doc["url"],
            "change_type": analysis["change_type"],
            "confidence_score": analysis["confidence"],
            "evidence": analysis["evidence"],
            "suggested_content": analysis.get("suggested_content"),
            "matched_entity": doc["matched_entity"]
        }
    
    def _format_event_for_claude(self, event: Dict) -> str:
        """Format event payload for Claude in readable way."""
        if event["source"] == "github" and event["event_type"] == "pull_request":
            pr = event["raw_payload"]["pull_request"]
            return f"""
Title: {pr['title']}
Description: {pr['body']}
Author: {pr['user']['login']}
Files Changed: {len(pr.get('files', []))}
Merged: {pr['merged']}
"""
        
        # Add more formatters for other event types
        return str(event["raw_payload"])
    
    def _parse_json(self, text: str) -> Dict:
        """Parse JSON from Claude response."""
        import json
        import re
        
        # Extract JSON from markdown code blocks if present
        json_match = re.search(r'```json\n(.*?)\n```', text, re.DOTALL)
        if json_match:
            text = json_match.group(1)
        
        return json.loads(text)
```

---

### Update Generator (Surgical Edits)

```python
# app/agents/update_generator.py

from typing import Dict, List
from app.agents.claude_client import ClaudeClient

class UpdateGenerator:
    """
    Generates surgical edits for documentation.
    
    Key Principles:
    1. Surgical edits (not full rewrites)
    2. Show clear before/after diffs
    3. Preserve existing style and tone
    4. Include source references
    """
    
    def __init__(self, claude: ClaudeClient):
        self.claude = claude
    
    async def generate_update(
        self,
        event: Dict,
        doc_content: str,
        section_identifier: str,
        change_type: str,
        evidence: Dict
    ) -> Dict:
        """
        Generate surgical edit for documentation.
        
        Returns:
        - original_content: the text being replaced
        - proposed_content: the new text
        - diff_markdown: formatted diff
        - explanation: human-readable explanation
        """
        # Extract the specific section to update
        section_content = self._extract_section(
            doc_content,
            section_identifier
        )
        
        prompt = f"""
Generate a SURGICAL EDIT for documentation. Update only what needs to change.

CONTEXT:
Change Type: {change_type}
Event: {self._format_event(event)}
Evidence: {evidence}

CURRENT DOCUMENTATION SECTION:
```
{section_content}
```

REQUIREMENTS:
1. Make MINIMAL changes - only update what's outdated
2. Preserve existing style, tone, and formatting
3. Keep all unrelated information unchanged
4. If adding new content, place it logically
5. Include source reference: "(updated {event['source']} #{event['event_id']}, {date})"

OUTPUT:
Provide the updated section that would replace the current one.

Important:
- Don't rewrite unnecessarily
- Don't change wording unless it's wrong
- Don't add fluff or marketing language
- DO fix factual errors
- DO add missing critical information
- DO mark deprecations clearly
"""
        
        proposed_content = await self.claude.generate(prompt)
        
        # Generate diff
        diff = self._generate_diff(section_content, proposed_content)
        
        # Generate explanation
        explanation = await self._generate_explanation(
            event,
            section_content,
            proposed_content,
            evidence
        )
        
        return {
            "original_content": section_content,
            "proposed_content": proposed_content,
            "diff_markdown": diff,
            "explanation": explanation
        }
    
    def _extract_section(self, content: str, identifier: str) -> str:
        """
        Extract specific section from doc content.
        
        Identifier formats:
        - "line 45": Single line
        - "lines 45-52": Range
        - "## Section Name": Markdown section
        - "paragraph containing 'rate limit'": Search-based
        """
        if identifier.startswith("line "):
            # Single line
            line_num = int(identifier.split()[1])
            lines = content.split("\n")
            return lines[line_num - 1] if line_num <= len(lines) else content
        
        elif identifier.startswith("lines "):
            # Range
            start, end = map(int, identifier.split()[1].split("-"))
            lines = content.split("\n")
            return "\n".join(lines[start-1:end])
        
        elif identifier.startswith("##"):
            # Markdown section
            # Extract from this heading to next heading of same level
            lines = content.split("\n")
            section_lines = []
            in_section = False
            heading_level = identifier.count("#")
            
            for line in lines:
                if line.strip() == identifier.strip():
                    in_section = True
                    section_lines.append(line)
                elif in_section:
                    if line.startswith("#" * heading_level + " "):
                        break
                    section_lines.append(line)
            
            return "\n".join(section_lines)
        
        elif "containing" in identifier:
            # Search-based
            search_term = identifier.split("'")[1]
            paragraphs = content.split("\n\n")
            for para in paragraphs:
                if search_term.lower() in para.lower():
                    return para
        
        # Fallback: return full content
        return content
    
    def _generate_diff(self, original: str, proposed: str) -> str:
        """
        Generate unified diff in markdown format.
        """
        import difflib
        
        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            proposed.splitlines(keepends=True),
            lineterm="",
            n=3  # context lines
        )
        
        # Format as markdown code block
        diff_text = "".join(diff)
        return f"```diff\n{diff_text}\n```"
    
    async def _generate_explanation(
        self,
        event: Dict,
        original: str,
        proposed: str,
        evidence: Dict
    ) -> str:
        """
        Generate human-readable explanation of the change.
        """
        prompt = f"""
Explain this documentation update in 2-3 sentences for a human reviewer.

EVENT: {self._format_event(event)}

CHANGE:
Before: {original[:200]}...
After: {proposed[:200]}...

Evidence: {evidence}

Write a clear, concise explanation that helps someone quickly understand:
1. What changed in the codebase/product
2. Why the docs need updating
3. What specifically is being updated

Keep it under 100 words. Be specific, not generic.
"""
        
        explanation = await self.claude.generate(prompt)
        return explanation.strip()
    
    def _format_event(self, event: Dict) -> str:
        """Format event for prompts."""
        return f"{event['source']} {event['event_type']} #{event['event_id']}"
```

---

### Approver Router

```python
# app/agents/approver_router.py

from typing import Dict, List, Optional

class ApproverRouter:
    """
    Determines who should approve a doc update.
    
    Routing Strategies:
    1. PR Author (they know the change best)
    2. CODEOWNERS (designated doc maintainers)
    3. Historical approver (who usually approves this doc)
    4. Confidence-based (high confidence = single approver, low = multiple)
    """
    
    def __init__(self, github_client):
        self.github = github_client
        self.codeowners_cache = {}
    
    def get_approver(
        self,
        event: Dict,
        doc_update: Dict
    ) -> Dict:
        """
        Determine approver for this update.
        
        Returns:
        - approver: GitHub username
        - approval_method: 'github_pr', 'notion_comment', 'slack_dm'
        - reasoning: why this person
        """
        # Strategy 1: PR author (if event is from PR)
        if event["source"] == "github" and "pull_request" in event["raw_payload"]:
            pr_author = event["raw_payload"]["pull_request"]["user"]["login"]
            
            return {
                "approver": pr_author,
                "approval_method": "github_pr",
                "reasoning": f"PR author who made the change"
            }
        
        # Strategy 2: CODEOWNERS
        if doc_update["doc_platform"] == "github":
            owner = self._get_codeowner(doc_update["doc_path"])
            if owner:
                return {
                    "approver": owner,
                    "approval_method": "github_pr",
                    "reasoning": f"CODEOWNERS for {doc_update['doc_path']}"
                }
        
        # Strategy 3: Default to repo admin
        # (In production, would query DB for historical approvers)
        return {
            "approver": os.getenv("DEFAULT_APPROVER"),
            "approval_method": "github_pr",
            "reasoning": "Default documentation maintainer"
        }
    
    def _get_codeowner(self, file_path: str) -> Optional[str]:
        """
        Parse CODEOWNERS file to find owner of this file.
        """
        if not self.codeowners_cache:
            self._load_codeowners()
        
        # Match path to CODEOWNERS patterns
        for pattern, owners in self.codeowners_cache.items():
            if self._path_matches(file_path, pattern):
                return owners[0] if owners else None
        
        return None
    
    def _load_codeowners(self):
        """Load and parse CODEOWNERS file from repo."""
        try:
            content = self.github.get_file_content(
                os.getenv("GITHUB_REPO"),
                ".github/CODEOWNERS"
            )
            
            for line in content.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                parts = line.split()
                pattern = parts[0]
                owners = [o.lstrip("@") for o in parts[1:]]
                self.codeowners_cache[pattern] = owners
        
        except Exception as e:
            print(f"Could not load CODEOWNERS: {e}")
    
    def _path_matches(self, path: str, pattern: str) -> bool:
        """Check if file path matches CODEOWNERS pattern."""
        import fnmatch
        return fnmatch.fnmatch(path, pattern)
```

---

## 🎬 Demo Setup

### Creating Demo Environment

```python
# demo/setup_demo.py

"""
Sets up a demo environment with:
1. Sample documentation files
2. Sample PRs to merge during demo
3. Test data in database
"""

import os
from github import Github

def setup_demo():
    """Run this before the hackathon to prepare demo."""
    
    # 1. Create demo GitHub repo with docs
    create_demo_repo()
    
    # 2. Create draft PRs for live demo
    create_demo_prs()
    
    # 3. Set up Notion pages
    create_notion_pages()
    
    print("✅ Demo environment ready!")
    print("\nNext steps:")
    print("1. Start server: uvicorn app.main:app --reload")
    print("2. Start ngrok: ngrok http 8000")
    print("3. Update GitHub webhook URL with ngrok URL")
    print("4. Merge demo PRs to trigger agent")

def create_demo_repo():
    """Create/update demo repo with sample docs."""
    gh = Github(os.getenv("GITHUB_TOKEN"))
    repo = gh.get_repo(os.getenv("GITHUB_DEMO_REPO"))
    
    # Create sample API docs
    api_docs = """# API Documentation

## Authentication

All API requests require authentication using an API key.

Rate limit: 100 requests per minute

## Endpoints

### GET /api/v2/users
Fetch user list...
"""
    
    repo.create_file(
        path="docs/api.md",
        message="docs: Add API documentation",
        content=api_docs,
        branch="main"
    )
    
    # Create README
    readme = """# Product Documentation

Welcome to our product docs!

## Features
- User management
- API access
- Analytics dashboard
"""
    
    repo.create_file(
        path="README.md",
        message="docs: Add README",
        content=readme,
        branch="main"
    )

def create_demo_prs():
    """Create PRs that will be merged during demo."""
    gh = Github(os.getenv("GITHUB_TOKEN"))
    repo = gh.get_repo(os.getenv("GITHUB_DEMO_REPO"))
    
    # PR 1: Rate limit change
    pr1_branch = "feature/increase-rate-limit"
    repo.create_git_ref(
        ref=f"refs/heads/{pr1_branch}",
        sha=repo.get_branch("main").commit.sha
    )
    
    # Just create the branch, don't modify code
    # (We'll merge during demo to trigger webhook)
    
    pr1 = repo.create_pull(
        title="Increase API rate limit to 200/min",
        body="""
## Changes
- Updated rate limiter configuration
- Increased limit from 100 to 200 requests/min
- Added rate limit headers to response

## Testing
- Tested with load testing tool
- Confirmed new limits work correctly
        """,
        head=pr1_branch,
        base="main"
    )
    
    print(f"Created PR #1: {pr1.html_url}")
    print("⚠️  Do NOT merge yet - merge during demo!")
    
    # PR 2: New OAuth feature
    pr2_branch = "feature/oauth-support"
    repo.create_git_ref(
        ref=f"refs/heads/{pr2_branch}",
        sha=repo.get_branch("main").commit.sha
    )
    
    pr2 = repo.create_pull(
        title="Add OAuth 2.0 authentication support",
        body="""
## Changes
- Implemented OAuth 2.0 client credentials flow
- Added `/oauth/token` endpoint
- Updated authentication middleware

## Documentation Needed
- API authentication section needs OAuth guide
- Need code examples for OAuth flow
        """,
        head=pr2_branch,
        base="main"
    )
    
    print(f"Created PR #2: {pr2.html_url}")

def create_notion_pages():
    """Create Notion pages for demo."""
    # TODO: Implement if using Notion in demo
    pass

if __name__ == "__main__":
    setup_demo()
```

---

## 🧪 Testing Strategy

### Unit Tests

```python
# tests/test_change_detection.py

import pytest
from app.agents.change_detector import ChangeDetector
from tests.fixtures.sample_events import SAMPLE_PR_EVENT

@pytest.mark.asyncio
async def test_detect_api_change():
    """Test detection of API rate limit change."""
    detector = ChangeDetector(mock_claude, mock_github, mock_notion)
    
    updates = await detector.analyze_event(SAMPLE_PR_EVENT)
    
    assert len(updates) > 0
    assert updates[0]["change_type"] == "modify"
    assert updates[0]["confidence_score"] > 0.7
    assert "rate limit" in updates[0]["evidence"]["event_signals"][0].lower()

@pytest.mark.asyncio
async def test_no_update_needed():
    """Test that irrelevant PRs don't trigger updates."""
    event = {
        "source": "github",
        "event_type": "pull_request",
        "raw_payload": {
            "pull_request": {
                "title": "Fix typo in internal comment",
                "body": "Just fixing a code comment",
                "merged": True
            }
        }
    }
    
    detector = ChangeDetector(mock_claude, mock_github, mock_notion)
    updates = await detector.analyze_event(event)
    
    assert len(updates) == 0  # Should not suggest doc update for typo
```

### Integration Tests

```python
# tests/test_end_to_end.py

@pytest.mark.asyncio
async def test_full_workflow():
    """Test complete workflow: webhook → detection → PR creation."""
    
    # 1. Simulate GitHub webhook
    response = await client.post(
        "/webhook/github",
        json=SAMPLE_PR_EVENT,
        headers={"X-Hub-Signature-256": generate_signature(SAMPLE_PR_EVENT)}
    )
    assert response.status_code == 200
    
    # 2. Wait for processing
    await asyncio.sleep(2)
    
    # 3. Check database for doc_update
    updates = db.query(DocUpdate).filter_by(status="pending").all()
    assert len(updates) > 0
    
    # 4. Verify GitHub PR was created
    # (mock or check actual GitHub API)
```

---

## 🚀 Deployment Guide

### Environment Variables

```bash
# .env.example

# GitHub
GITHUB_TOKEN=ghp_...
GITHUB_WEBHOOK_SECRET=...
GITHUB_REPO=username/repo-name
GITHUB_DEMO_REPO=username/demo-repo

# Notion (optional)
NOTION_TOKEN=secret_...
NOTION_DATABASE_ID=...

# Claude
ANTHROPIC_API_KEY=sk-ant-...

# Database
DATABASE_URL=sqlite:///./docs_agent.db  # Local
# DATABASE_URL=postgresql://...  # Production

# Server
ENVIRONMENT=development  # or 'production'
LOG_LEVEL=INFO
DEFAULT_APPROVER=your-github-username

# Ngrok (local only)
NGROK_AUTHTOKEN=...
```

### Local Development with ngrok

```bash
# Terminal 1: Start server
uvicorn app.main:app --reload --port 8000

# Terminal 2: Start ngrok
ngrok http 8000

# Copy ngrok URL (e.g., https://abc123.ngrok.io)
# Update GitHub webhook URL:
# https://abc123.ngrok.io/webhook/github
```

### Docker Deployment

```dockerfile
# Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/
COPY demo/ ./demo/

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml

version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/docs_agent
    env_file:
      - .env
    depends_on:
      - db
  
  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=docs_agent
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### Production Deployment (Railway/Render)

```bash
# Option 1: Railway
railway login
railway init
railway up

# Option 2: Render
# Connect GitHub repo
# Set environment variables in dashboard
# Deploy automatically on push
```

---

## 📊 Success Metrics

### For Hackathon Demo
- [ ] Successfully receives GitHub webhooks
- [ ] Detects changes requiring doc updates (>50% accuracy)
- [ ] Generates surgical edits (not full rewrites)
- [ ] Creates GitHub PRs with clear diffs
- [ ] Routes to correct approver
- [ ] Shows confidence scores + evidence
- [ ] Processes demo PR in <30 seconds

### For Real Product
- Accuracy: >80% of suggested updates are approved
- Speed: <1 minute from event to PR creation
- Adoption: >50% of team uses it regularly
- Impact: Doc staleness reduced from months to days

---

## 🗓️ Implementation Timeline

### Pre-Hackathon (Tonight)
- [ ] Set up GitHub repo with sample docs
- [ ] Create GitHub webhook
- [ ] Set up ngrok
- [ ] Test webhook delivery
- [ ] Get Claude API key
- [ ] Create demo PRs (don't merge yet)

### Hour 0-2: Foundation
- [ ] FastAPI server with health check
- [ ] GitHub webhook endpoint
- [ ] Signature validation
- [ ] Event storage (SQLite)
- [ ] Basic logging

### Hour 3-4: Detection Engine
- [ ] Claude integration
- [ ] Entity extraction from events
- [ ] Document search (GitHub)
- [ ] Change detection logic
- [ ] Confidence scoring

### Hour 5-6: Update Generation
- [ ] Surgical edit generation
- [ ] Diff generation
- [ ] Evidence trail
- [ ] GitHub PR creation
- [ ] Approver routing

### Hour 7-8: Demo Polish
- [ ] Test with real PRs
- [ ] Add demo scenarios
- [ ] Create presentation
- [ ] Practice pitch
- [ ] Backup recordings

---

## 🎤 Demo Script

### Introduction (1 minute)
```
"Documentation goes stale because updating it feels like homework.

We built an AI agent that watches where work happens,
detects when docs become outdated,
and drafts surgical updates—
you just say yes or no.

Let me show you."
```

### Demo (3 minutes)

**Act 1: Setup (30s)**
```
"This is our GitHub repo with API documentation.
Currently says rate limit is 100 requests per minute.

But our engineer just finished a PR to increase it to 200.
Let's merge it and watch what happens."
```

**Act 2: The Magic (60s)**
```
[Merge PR]

"Within seconds, our agent:
1. Detected the PR merge
2. Extracted 'rate limit: 200' from the changes
3. Searched our docs for 'rate limit'
4. Found this section in our API docs
5. Generated a surgical edit

Let's look at what it created..."

[Show GitHub PR created by agent]

"Here's the PR our agent created.
Notice:
- It only changed ONE line
- Shows clear before/after diff  
- Includes confidence score: 0.95
- Shows evidence: links to the original PR
- Assigned to Alice, who wrote the code

This is surgical, not a rewrite."
```

**Act 3: Human Approval (30s)**
```
"Alice gets notified.
She reviews the diff in 10 seconds.
Approves.
Docs are updated.

Total time: 30 seconds.
Without this: She wouldn't remember,
docs would be stale for months."
```

**Act 4: The Vision (30s)**
```
"This works across platforms:
- GitHub PRs → API docs
- Linear tickets → Feature docs
- Slack decisions → Internal wikis

And it's not just for developers.
Sales decks, support guides, onboarding docs—
all kept fresh automatically."
```

### Q&A Prep
**Q: What if it makes mistakes?**
A: That's why humans approve. It's an assistant, not autopilot. Plus we show confidence scores and evidence.

**Q: How do you handle conflicts?**
A: Updates are small and surgical. If conflicts occur, we alert the human and show both versions.

**Q: Why not just use Notion AI?**
A: Notion AI waits for you to ask. We're proactive. And we watch GitHub, Linear, Slack—not just Notion.

---

## 🔮 Future Enhancements (Post-Hackathon)

### Phase 2: Smart Features
- [ ] Learning from approvals (what gets accepted vs rejected)
- [ ] Auto-approve high-confidence, low-risk updates
- [ ] Multi-doc updates (update sales deck + API docs together)
- [ ] Notification preferences per user

### Phase 3: More Platforms
- [ ] Linear integration
- [ ] Slack integration (messages as doc source)
- [ ] Jira integration
- [ ] Confluence direct integration

### Phase 4: Advanced AI
- [ ] Style preservation (match doc's writing style)
- [ ] Screenshot/diagram updates
- [ ] Code example generation
- [ ] Multi-language docs (i18n)

---

## 📝 Notes for Coding Agent

### Key Implementation Priorities

1. **Start with GitHub only**
   - Get webhooks working reliably
   - Nail the PR creation workflow
   - GitHub is both source and target (simpler)

2. **Claude integration is critical**
   - Use Claude 3.5 Sonnet (best reasoning)
   - Cache system prompts to save costs
   - Handle rate limits gracefully

3. **Keep it simple**
   - SQLite is fine for hackathon
   - Don't over-engineer database
   - Focus on core workflow

4. **Error handling**
   - Log everything
   - Fail gracefully
   - Retry webhook processing if Claude times out

5. **Security**
   - Validate ALL webhook signatures
   - Never expose tokens in logs
   - Use environment variables

### Code Quality Standards
- Type hints on all functions
- Docstrings for public APIs
- Error messages should be actionable
- Log structured data (JSON logs)

### Testing Priority
1. Webhook signature validation (security critical)
2. Claude prompt correctness (accuracy critical)
3. GitHub PR creation (demo critical)
4. Everything else (nice to have)

---

## ✅ Definition of Done

### MVP is complete when:
- [ ] GitHub webhook receives and validates PR events
- [ ] Claude analyzes PRs and detects doc changes
- [ ] System searches GitHub repo for affected docs
- [ ] Surgical edits are generated with diffs
- [ ] GitHub PRs are created with updates
- [ ] Confidence scores and evidence are shown
- [ ] Demo works end-to-end 3 times in a row
- [ ] Can explain the system in <3 minutes

### Bonus points if:
- [ ] Notion integration works
- [ ] Deployed to cloud (not just ngrok)
- [ ] Has a simple dashboard UI
- [ ] Handles multiple doc formats (md, rst, etc.)

---

## 🎯 Success Criteria for Judging

**What judges will love:**
- ✅ Live demo with real GitHub PR
- ✅ Clear before/after showing staleness problem
- ✅ Surgical edits (not AI rewrites)
- ✅ Confidence scores + evidence (trustworthy AI)
- ✅ Works cross-functionally (not just dev docs)

**What will make you stand out:**
- The "approve, not write" framing
- Event-driven detection (not vague staleness)
- Real integrations (not mocks)
- Thoughtful approval routing
- Clear path to production use

---

**END OF PRD**

This document should provide everything needed for a coding agent to implement the system. Questions or clarifications? Add them as comments in the codebase or update this PRD.