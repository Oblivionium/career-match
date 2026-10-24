"""Central configuration, read from environment variables (.env)."""

import os

from dotenv import load_dotenv
from uagents_core.identity import Identity

load_dotenv()


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def address_for_seed(seed: str) -> str:
    """Agent addresses are derived from seeds, so we can compute them without running the agent."""
    return Identity.from_seed(seed, 0).address


# --- Agent seeds (keep these secret; they define each agent's identity) -------------
COORD_SEED = env("COORD_SEED", "career-coordinator-dev-seed-change-me")
RESUME_SEED = env("RESUME_SEED", "resume-analyst-dev-seed-change-me")
SCOUT_SEED = env("SCOUT_SEED", "job-scout-dev-seed-change-me")
MATCH_SEED = env("MATCH_SEED", "match-apply-dev-seed-change-me")

# Addresses can be overridden (e.g. if an agent is hosted elsewhere); otherwise derived.
RESUME_ADDR = env("RESUME_ADDR") or address_for_seed(RESUME_SEED)
SCOUT_ADDR = env("SCOUT_ADDR") or address_for_seed(SCOUT_SEED)
MATCH_ADDR = env("MATCH_ADDR") or address_for_seed(MATCH_SEED)

# --- Ports ----------------------------------------------------------------------------
COORD_PORT = env_int("COORD_PORT", 8001)
RESUME_PORT = env_int("RESUME_PORT", 8002)
SCOUT_PORT = env_int("SCOUT_PORT", 8003)
MATCH_PORT = env_int("MATCH_PORT", 8004)

USE_MAILBOX = env_bool("USE_MAILBOX", True)

# --- ASI:One LLM ------------------------------------------------------------------------
ASI_ONE_API_KEY = env("ASI_ONE_API_KEY")
ASI_ONE_BASE_URL = env("ASI_ONE_BASE_URL", "https://api.asi1.ai/v1")
ASI_ONE_MODEL = env("ASI_ONE_MODEL", "asi1")
GEMINI_API_KEY = env("GEMINI_API_KEY")
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-2.5-flash")

# --- Job sources ------------------------------------------------------------------------
ADZUNA_APP_ID = env("ADZUNA_APP_ID")
ADZUNA_APP_KEY = env("ADZUNA_APP_KEY")
ADZUNA_COUNTRY = env("ADZUNA_COUNTRY", "in")
JSEARCH_API_KEY = env("JSEARCH_API_KEY")  # RapidAPI key
JOB_CACHE_TTL_SECONDS = env_int("JOB_CACHE_TTL_SECONDS", 1800)
# Comma-separated source names to force-fail, for demonstrating fallback in the demo video.
SIMULATE_SOURCE_FAILURE = {
    s.strip() for s in env("SIMULATE_SOURCE_FAILURE").split(",") if s.strip()
}

# --- Payments ----------------------------------------------------------------------------
PAYMENTS_ENABLED = env_bool("PAYMENTS_ENABLED", True)
PACK_PRICE_FET = env("PACK_PRICE_FET", "0.5")
FET_USE_TESTNET = env_bool("FET_USE_TESTNET", True)
# Wallet that receives payments. Defaults to the coordinator agent's own wallet.
PAYMENT_WALLET = env("PAYMENT_WALLET")

# --- Timeouts ----------------------------------------------------------------------------
WORKER_TIMEOUT = env_int("WORKER_TIMEOUT", 60)
