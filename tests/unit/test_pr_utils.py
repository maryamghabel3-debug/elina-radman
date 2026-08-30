from unittest.mock import patch, MagicMock

import pytest

from scripts.dev.pr_utils import create_pr

pytestmark = pytest.mark.unit

REPO = "maryamghabel3-debug/elina-radman"
TOKEN = "test-token-never-printed"
BODY = "## Summary\n\nSafe PR body."


def _mock_response(json_data):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


def test_create_pr_payload_uses_body_not_body_file():
    """The POST payload must carry the description in the valid 'body' field
    (the 'body_file' field does not exist in the GitHub REST API)."""
    pr_json = {"number": 100, "html_url": "https://github.com/x/pull/100", "body": BODY}
    with patch("scripts.dev.pr_utils.requests") as mock_requests:
        mock_requests.post.return_value = _mock_response(pr_json)
        mock_requests.get.return_value = _mock_response(pr_json)

        result = create_pr(REPO, "main", "feat/x", "feat: x", BODY, TOKEN)

    # POST payload check
    post_kwargs = mock_requests.post.call_args[1]
    payload = post_kwargs["json"]
    assert payload["body"] == BODY
    assert "body_file" not in payload
    assert payload["title"] == "feat: x"
    assert payload["base"] == "main"
    assert payload["head"] == "feat/x"
    # token only in the Authorization header, never in the payload
    assert post_kwargs["headers"]["Authorization"] == f"token {TOKEN}"
    assert TOKEN not in str(payload)
    # verified on the server and returned
    assert mock_requests.get.call_count == 1
    get_url = mock_requests.get.call_args[0][0]
    assert get_url.endswith(f"/repos/{REPO}/pulls/100")
    assert result["number"] == 100


def test_create_pr_empty_server_body_raises():
    """If the server-side body ends up empty, raise PR_BODY_EMPTY_AFTER_CREATE."""
    pr_json = {"number": 101, "body": "   "}
    with patch("scripts.dev.pr_utils.requests") as mock_requests:
        mock_requests.post.return_value = _mock_response(pr_json)
        mock_requests.get.return_value = _mock_response(pr_json)

        with pytest.raises(RuntimeError, match="PR_BODY_EMPTY_AFTER_CREATE"):
            create_pr(REPO, "main", "feat/x", "feat: x", BODY, TOKEN)


def test_create_pr_empty_body_field_missing_also_raises():
    """A PR JSON without a 'body' key at all must also raise."""
    pr_json = {"number": 102}
    with patch("scripts.dev.pr_utils.requests") as mock_requests:
        mock_requests.post.return_value = _mock_response(pr_json)
        mock_requests.get.return_value = _mock_response(pr_json)

        with pytest.raises(RuntimeError, match="PR_BODY_EMPTY_AFTER_CREATE"):
            create_pr(REPO, "main", "feat/x", "feat: x", BODY, TOKEN)


def test_create_pr_non_empty_body_succeeds():
    """A non-empty server body returns the created PR JSON."""
    pr_json = {"number": 103, "html_url": "https://github.com/x/pull/103", "body": BODY}
    with patch("scripts.dev.pr_utils.requests") as mock_requests:
        mock_requests.post.return_value = _mock_response(pr_json)
        mock_requests.get.return_value = _mock_response(pr_json)

        result = create_pr(REPO, "main", "feat/x", "feat: x", BODY, TOKEN)

    assert result["number"] == 103
    assert result["body"].strip() == BODY.strip()


def test_create_pr_rejects_empty_body_text_upfront():
    """Empty/whitespace body_text is rejected before any API call."""
    with patch("scripts.dev.pr_utils.requests") as mock_requests:
        with pytest.raises(ValueError):
            create_pr(REPO, "main", "feat/x", "feat: x", "   ", TOKEN)
        mock_requests.post.assert_not_called()
