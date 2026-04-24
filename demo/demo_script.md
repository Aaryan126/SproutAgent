# Demo Script

## Setup (before presenting)

- [ ] Server running: `uvicorn app.main:app --reload --port 8000`
- [ ] ngrok running and webhook URL updated in GitHub
- [ ] Browser tabs open:
  1. GitHub repo — docs/api.md (showing "Rate limit: 100 requests per minute")
  2. GitHub repo — draft PR "Increase API rate limit to 200/min"
  3. `http://localhost:8000/dashboard/` (should show 0 events)
  4. GitHub PRs page (to watch for new auto-generated PR)

---

## Introduction (45s)

> "Documentation goes stale because updating it feels like homework.
>
> Engineers know the code changed — they just don't think to update the docs.
> By the time someone notices, it's months later.
>
> We built an AI agent that watches where work actually happens — GitHub PRs —
> detects when docs become outdated, and drafts a surgical fix.
>
> You just say yes or no."

---

## Act 1: Show the problem (20s)

Point to docs/api.md:

> "This is our API docs. Says rate limit is 100 requests per minute."

Point to draft PR:

> "Our engineer just increased it to 200. This PR is ready to merge.
> Without our agent, the docs would stay wrong indefinitely."

---

## Act 2: Merge and watch (60s)

Merge the PR. Switch to dashboard tab.

> "I just merged the PR. Let's watch what happens."

Refresh dashboard after ~10s:

> "The agent already received the webhook, extracted 'rate limit' from the PR,
> searched the docs, and is generating a fix."

After ~20-30s, switch to GitHub PRs tab:

> "Here's the PR our agent just created.
>
> Notice:
> - It changed exactly ONE line
> - Clear before/after diff
> - Confidence score with evidence — why it thinks this needs updating
> - Assigned to Alice, the engineer who made the change"

---

## Act 3: Human approval (20s)

> "Alice gets notified. She looks at the diff — takes 10 seconds.
> She approves. Docs are updated.
>
> Total time from merge to fix: under 30 seconds.
> Without this: probably never."

---

## Act 4: The vision (30s)

> "This works across any code change that affects documentation.
> API changes, config changes, deprecations, new features.
>
> The key insight: we're not trying to write docs automatically.
> We're trying to make it impossible to forget to update them.
>
> The human still decides. The agent just makes sure they're asked."

---

## Q&A Prep

**Q: What if it makes mistakes?**
> Humans always approve. We show confidence scores and evidence so reviewers can make informed decisions quickly.

**Q: How accurate is it?**
> In our testing, above 0.7 confidence the edits are almost always correct. Below that it flags for human judgment.

**Q: Why not just use Notion AI or GitHub Copilot?**
> Those wait for you to ask. We're proactive — we watch what's being merged and act on it automatically.

**Q: What about large docs or many PRs?**
> We limit to top matching docs per PR, and only flag docs with confidence above a configurable threshold.
