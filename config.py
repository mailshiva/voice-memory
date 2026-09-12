import os
import sys
from dotenv import load_dotenv

try:
    import keyring  # only usable on macOS — see _get_secret below
except ImportError:
    keyring = None

load_dotenv()

KEYRING_SERVICE = "voice-memory-bot"
IS_MACOS = sys.platform == "darwin"


def _get_secret(name: str, env_var: str) -> str:
    """On macOS, look up the secret in Keychain via `keyring`. On any other
    platform (e.g. a Linux cloud VM, which has no Keychain), skip straight
    to an environment variable / .env entry instead."""
    if IS_MACOS and keyring is not None:
        try:
            value = keyring.get_password(KEYRING_SERVICE, name)
            if value:
                return value
        except Exception:
            pass  # no Keychain daemon reachable, etc. — fall through to env

    value = os.environ.get(env_var)
    if not value:
        source = "Keychain or .env" if IS_MACOS else ".env / environment variables"
        raise RuntimeError(f"Missing secret '{name}'. Set it via {source}.")
    return value


TELEGRAM_BOT_TOKEN = _get_secret("telegram_bot_token", "TELEGRAM_BOT_TOKEN")
SUPABASE_URL = _get_secret("supabase_url", "SUPABASE_URL")
SUPABASE_KEY = _get_secret("supabase_key", "SUPABASE_KEY")
GROQ_API_KEY = _get_secret("groq_api_key", "GROQ_API_KEY")

# Model used for both storing and querying — must stay consistent
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# How many past memories to retrieve per question
TOP_K = 5

# This is a single-user personal bot, so the one user's timezone is just
# hardcoded rather than made configurable per-chat. Used to resolve
# relative-date language in photo captions/content (e.g. a birthday-wish
# screenshot implying "today") against the day it actually was for the
# user, not the UTC day Telegram's message timestamp falls on.
USER_TIMEZONE = "America/Chicago"