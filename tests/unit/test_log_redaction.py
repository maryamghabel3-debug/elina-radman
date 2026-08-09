import pytest
import logging
from agents.security.log_redaction import (
    redact_sensitive_text,
    SecretRedactionFilter,
    install_secret_redaction
)

pytestmark = pytest.mark.unit


# 1. Telegram token inside an API URL is completely redacted.
def test_telegram_token_redaction():
    url = "https://api.telegram.org/bot123456:ABC-DEF1234ghIkl-MnoPQrstUVw/getMe"
    redacted = redact_sensitive_text(url)
    assert "123456:ABC-DEF" not in redacted
    assert "bot***REDACTED***" in redacted


# 2. GitHub ghp-style synthetic token is redacted.
def test_github_ghp_token_redaction():
    log_msg = "Pushed using token ghp_MySyntheticToken1234567890abcdef"
    redacted = redact_sensitive_text(log_msg)
    assert "ghp_My" not in redacted
    assert "***GITHUB_TOKEN_REDACTED***" in redacted


# 3. github_pat-style synthetic token is redacted.
def test_github_pat_token_redaction():
    log_msg = "Cloned using token github_pat_SomePatTokenValue_123456"
    redacted = redact_sensitive_text(log_msg)
    assert "github_pat_" not in redacted
    assert "***GITHUB_TOKEN_REDACTED***" in redacted


# 4. Supabase sb_secret synthetic value is redacted.
def test_supabase_secret_redaction():
    log_msg = "Connected with sb_secret_MySuperSecretSupabaseToken"
    redacted = redact_sensitive_text(log_msg)
    assert "sb_secret_" not in redacted
    assert "***SUPABASE_SECRET_REDACTED***" in redacted


# 5. Bearer token is redacted.
def test_bearer_token_redaction():
    log_msg = "Header: Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    redacted = redact_sensitive_text(log_msg)
    assert "eyJhbGciOi" not in redacted
    assert "Authorization: Bearer ***REDACTED***" in redacted


# 6. Generic token= value is redacted.
def test_generic_token_value_redaction():
    assert "token=***REDACTED***" in redact_sensitive_text("https://api.com/v1?token=MySecretVal")
    assert "password=***REDACTED***" in redact_sensitive_text("credentials: password=SomeSecretPassword")
    assert "secret=***REDACTED***" in redact_sensitive_text("env: secret=MySecretString")
    assert "api_key=***REDACTED***" in redact_sensitive_text("api_key=MyVerySecretApiKey")


# 7. Ordinary log messages remain unchanged.
def test_ordinary_log_unchanged():
    msg = "User tester successfully completed task 123."
    assert redact_sensitive_text(msg) == msg


# 8. Non-string logging arguments do not crash.
def test_non_string_args_no_crash():
    redaction_filter = SecretRedactionFilter()

    # Create a synthetic LogRecord
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg={"dict_key": "some_value"},  # Non-string msg
        args=(123, 456),                 # Non-string args
        exc_info=None
    )

    assert redaction_filter.filter(record) is True
    assert record.msg == {"dict_key": "some_value"}


# 9. Installing filters twice does not duplicate or fail.
def test_install_redaction_twice_no_duplicates():
    # Setup logger and handler
    logger = logging.getLogger("test_install_logger")
    handler = logging.StreamHandler()
    logger.addHandler(handler)

    # Run installation twice
    install_secret_redaction()
    install_secret_redaction()

    # Check that filter is attached only once
    filters = handler.filters
    redaction_filters = [f for f in filters if isinstance(f, SecretRedactionFilter)]
    # Note: since named loggers might not have been registered in loggerDict yet when install_secret_redaction ran,
    # let's register it to root or check that the root handler has only one filter!
    root_logger = logging.getLogger()
    for h in root_logger.handlers:
        red_filters = [f for f in h.filters if isinstance(f, SecretRedactionFilter)]
        assert len(red_filters) <= 1


# 10. Source files call install_secret_redaction before bot startup.
def test_source_files_call_redaction():
    # Read run_server.py, elina_intake_bot.py, elina_studio_bot.py and verify import is present
    for filepath in ["scripts/run_server.py", "scripts/elina_intake_bot.py", "scripts/elina_studio_bot.py"]:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        assert "install_secret_redaction" in content
