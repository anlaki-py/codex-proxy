"""Constants for the OpenAI Codex OAuth flow and API endpoints."""

from pathlib import Path

# OAuth constants (from pi-mono / OpenAI Codex CLI)
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"
CALLBACK_PORT = 1455
REDIRECT_URI = "http://localhost:1455/auth/callback"
SCOPE = "openid profile email offline_access"

# JWT claim path for account ID extraction
JWT_CLAIM_PATH = "https://api.openai.com/auth"

# ChatGPT backend API
CHATGPT_BACKEND_URL = "https://chatgpt.com/backend-api"
RESPONSES_ENDPOINT = f"{CHATGPT_BACKEND_URL}/codex/responses"
USAGE_ENDPOINT = f"{CHATGPT_BACKEND_URL}/wham/usage"

# Local storage
CONFIG_DIR = Path.home() / ".codex-proxy"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"
ACCOUNTS_DIR = CONFIG_DIR / "accounts"
REGISTRY_FILE = ACCOUNTS_DIR / "registry.json"

# Server defaults
DEFAULT_PORT = 8787
DEFAULT_HOST = "0.0.0.0"
DEFAULT_CODEX_MODEL = "gpt-5.6"

# ChatGPT-sign-in models documented for Codex as of 2026-08-15. GPT-5.4 and
# GPT-5.4 Mini remain available until 2026-08-31; Codex Spark requires ChatGPT Pro.
CODEX_MODEL_IDS = (
    "gpt-5.6",
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "gpt-5.5",
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.3-codex-spark",
)
CODEX_MODELS = [
    {"id": model_id, "object": "model", "owned_by": "openai"}
    for model_id in CODEX_MODEL_IDS
]
