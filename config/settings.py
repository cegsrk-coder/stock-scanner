"""
Configuration settings for the stock scanner.
Reads secrets from environment variables (for GitHub Actions / cloud).
Falls back to local values for dev use.
"""

import os
from pathlib import Path

# Load .env file if it exists (local dev)
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _val = _line.split("=", 1)
                os.environ.setdefault(_key.strip(), _val.strip())

# 5paisa API Credentials (set via environment variables or .env file)
FIVE_PAISA_CRED = {
    "APP_SOURCE": os.environ.get("FIVE_PAISA_APP_SOURCE", ""),
    "APP_NAME": os.environ.get("FIVE_PAISA_APP_NAME", ""),
    "USER_ID": os.environ.get("FIVE_PAISA_USER_ID", ""),
    "PASSWORD": os.environ.get("FIVE_PAISA_PASSWORD", ""),
    "USER_KEY": os.environ.get("FIVE_PAISA_USER_KEY", ""),
    "ENCRYPTION_KEY": os.environ.get("FIVE_PAISA_ENCRYPTION_KEY", ""),
}

# 5paisa login details
CLIENT_CODE = os.environ.get("FIVE_PAISA_CLIENT_CODE", "")
TOTP_SECRET = os.environ.get("FIVE_PAISA_TOTP_SECRET", "")
PIN = os.environ.get("FIVE_PAISA_PIN", "")

# Scanner settings
LOOKBACK_YEARS = 2  # How many years of weekly data to analyze
PROXIMITY_PCT = 3.0  # Alert when price is within this % of a support/resistance zone
ZONE_CLUSTER_PCT = 2.0  # Group swing points within this % into a single zone
MIN_TOUCHES = 2  # Minimum touches to consider a zone valid

# Data source settings
JUGAAD_DELAY_SECONDS = 0.3  # Delay between jugaad-data API calls to avoid NSE rate limiting

# Report settings
REPORT_DIR = "reports"

# Telegram Bot settings (set via environment variables or .env file)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
