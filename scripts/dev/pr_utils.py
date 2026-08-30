"""
Safe GitHub PR creation helper (dev-only, for agent workflows).

Incident background: PRs #87, #88, and #89 were opened with a hand-rolled
payload that used `body_file` -- which is NOT a valid GitHub REST API
parameter. GitHub silently ignored the unknown field, so all three PRs
were created with empty descriptions until manually patched.

This helper guarantees:
- the PR description is sent in the correct `body` field (never `body_file`),
- the PR is re-fetched after creation and the server-side body is verified
  non-empty, failing loudly with PR_BODY_EMPTY_AFTER_CREATE otherwise,
- the token is only ever placed in the Authorization header (never printed).

Uses `requests` (already pinned in requirements-core.txt) -- no new deps.
"""

import requests

GITHUB_API_BASE = "https://api.github.com"


def create_pr(repo: str, base: str, head: str, title: str, body_text: str, token: str) -> dict:
    """
    Creates a PR using the correct 'body' field (never body_file).
    Fails loudly if the resulting PR body is empty on the server.
    Returns the created PR JSON (as re-fetched from the server).
    """
    if not isinstance(body_text, str) or not body_text.strip():
        raise ValueError("body_text must be a non-empty string (empty PR bodies are not allowed)")

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }

    # `body` is the ONLY valid field for the PR description.
    payload = {
        "title": title,
        "head": head,
        "base": base,
        "body": body_text,
    }

    resp = requests.post(
        f"{GITHUB_API_BASE}/repos/{repo}/pulls",
        headers=headers,
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    pr = resp.json()
    pr_number = pr["number"]

    # Verify on the server: the body must actually be present.
    check = requests.get(
        f"{GITHUB_API_BASE}/repos/{repo}/pulls/{pr_number}",
        headers=headers,
        timeout=30,
    )
    check.raise_for_status()
    created = check.json()

    if not (created.get("body") or "").strip():
        raise RuntimeError("PR_BODY_EMPTY_AFTER_CREATE")

    return created
