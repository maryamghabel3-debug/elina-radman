# Dev: PR utilities

Safe helpers for agent workflows. Do NOT import from production code paths.

## `create_pr` — always use this instead of hand-rolling the GitHub API payload

    import os
    from scripts.dev.pr_utils import create_pr

    pr = create_pr(repo="maryamghabel3-debug/elina-radman", base="main", head="feat/my-branch",
                   title="feat(...): my change", body_text="## Summary\n\nWhat changed and why.",
                   token=os.environ["GITHUB_TOKEN"])  # never print the token
    print(f"PR #{pr['number']}: {pr['html_url']}")

Sends the description in the valid `body` field (never `body_file`), then
re-fetches the PR and raises `RuntimeError("PR_BODY_EMPTY_AFTER_CREATE")` if
the server-side description is empty.
