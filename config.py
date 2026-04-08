"""Shared configuration -- loads secrets from environment or .streamlit/secrets.toml."""

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Try Streamlit secrets first (for Streamlit Cloud), then env vars
try:
    import streamlit as st
    _secrets = st.secrets
except Exception:
    _secrets = {}


def _get(key: str, default: str = "") -> str:
    """Get a secret from Streamlit secrets, env vars, or default."""
    if _secrets and key in _secrets:
        return _secrets[key]
    return os.environ.get(key, default)


# ─── API Keys ────────────────────────────────────────────────────────────────

OPENAI_API_KEY = _get("OPENAI_API_KEY")
SUPABASE_URL = _get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = _get("SUPABASE_SERVICE_KEY")

NEO4J_URI = _get("NEO4J_URI")
NEO4J_USER = _get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = _get("NEO4J_PASSWORD")

# ─── Supabase Headers ────────────────────────────────────────────────────────

SUPABASE_HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
}
