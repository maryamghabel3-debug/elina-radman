import re
import logging
from typing import Optional, Union

logger = logging.getLogger(__name__)


def redact_sensitive_text(value: str) -> str:
    if not isinstance(value, str):
        return str(value)

    # 1. Telegram bot tokens in URLs (e.g. bot123:abc)
    text = re.sub(r"bot\d+:[^\s/?&#]+", "bot***REDACTED***", value)

    # 2. GitHub tokens
    text = re.sub(r"ghp_[A-Za-z0-9_]+", "***GITHUB_TOKEN_REDACTED***", text)
    text = re.sub(r"github_pat_[A-Za-z0-9_]+", "***GITHUB_TOKEN_REDACTED***", text)

    # 3. Supabase secrets
    text = re.sub(r"sb_secret_[A-Za-z0-9_]+", "***SUPABASE_SECRET_REDACTED***", text)
    text = re.sub(r"eyJhbGciOi[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+", "***SUPABASE_SECRET_REDACTED***", text)

    # 4. Generic labels
    text = re.sub(r"(token|password|secret|api_key)=([^\s&]+)", r"\1=***REDACTED***", text, flags=re.IGNORECASE)
    text = re.sub(r"(Authorization:\s*Bearer\s+)([^\s]+)", r"\1***REDACTED***", text, flags=re.IGNORECASE)

    return text


class SecretRedactionFilter(logging.Filter):
    """
    Filter to permanently redact secrets from all log records.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            # Redact record.msg
            if record.msg and isinstance(record.msg, str):
                record.msg = redact_sensitive_text(record.msg)

            # Redact record.args
            if record.args:
                if isinstance(record.args, dict):
                    new_args = {}
                    for k, v in record.args.items():
                        if isinstance(v, str):
                            new_args[k] = redact_sensitive_text(v)
                        else:
                            new_args[k] = v
                    record.args = new_args
                elif isinstance(record.args, tuple):
                    new_args = []
                    for v in record.args:
                        if isinstance(v, str):
                            new_args.append(redact_sensitive_text(v))
                        else:
                            new_args.append(v)
                    record.args = tuple(new_args)
                elif isinstance(record.args, list):
                    new_args = []
                    for v in record.args:
                        if isinstance(v, str):
                            new_args.append(redact_sensitive_text(v))
                        else:
                            new_args.append(v)
                    record.args = new_args

            # Redact record.exc_text
            if record.exc_text:
                record.exc_text = redact_sensitive_text(record.exc_text)

        except Exception:
            # Safety first, never crash logging under any circumstances
            pass

        return True


_redactor_installed = False


def install_secret_redaction() -> None:
    global _redactor_installed
    if _redactor_installed:
        return

    redaction_filter = SecretRedactionFilter()

    # 1. Attach filter to the root logger handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if not any(isinstance(f, SecretRedactionFilter) for f in handler.filters):
            handler.addFilter(redaction_filter)

    # 2. Attach filter to all existing loggers' handlers
    for name in logging.root.manager.loggerDict:
        lgr = logging.getLogger(name)
        if hasattr(lgr, "handlers"):
            for handler in lgr.handlers:
                if not any(isinstance(f, SecretRedactionFilter) for f in handler.filters):
                    handler.addFilter(redaction_filter)

    # 3. Set noisy network loggers to WARNING
    for logger_name in ["httpx", "httpcore"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    _redactor_installed = True
