import os
from dotenv import load_dotenv

try:
    import keyring  # only meaningfully available on your Mac
except ImportError:
    keyring = None

load_dotenv()

KEYRING_SERVICE = "voice-memory-bot"


def _get_secret(name: str, env_var: str) -> str:
    """Look up a secret from macOS Keychain first (via `keyring`), then fall
    back to an environment variable / .env entry. Keychain won't exist on a
    Linux cloud server, so that fallback is what a cloud deployment uses."""
    if keyring is not None:
        value = keyring.get_password(KEYRING_SERVICE, name)
        if value:
            return value

    value = os.environ.get(env_var)
    if not value:
        raise RuntimeError(
            f"Missing secret '{name}'. Either store it in Keychain "
            f"(see README.md) or set {env_var} in your environment/.env file."
        )
    return value


TELEGRAM_BOT_TOKEN = _get_secret("telegram_bot_token", "TELEGRAM_BOT_TOKEN")
SUPABASE_URL = _get_secret("supabase_url", "SUPABASE_URL")
SUPABASE_KEY = _get_secret("supabase_key", "SUPABASE_KEY")
GROQ_API_KEY = _get_secret("groq_api_key", "GROQ_API_KEY")

# Model used for both storing and querying — must stay consistent
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# How many past memories to retrieve per question
TOP_K = 5
