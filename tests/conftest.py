import pytest
import os

# Set required environment variables for tests
os.environ.setdefault("OWNER_CHAT_ID", "12345")
os.environ.setdefault("STUDIO_BOT_TOKEN", "test_token_for_testing")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test_token")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test_key")
