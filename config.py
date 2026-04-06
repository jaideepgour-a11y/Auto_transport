"""
Configuration - load from environment variables.
Copy .env.example to .env and fill in your values.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Meta WhatsApp Cloud API
    WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN", "")           # Bearer token
    WHATSAPP_PHONE_ID: str = os.getenv("WHATSAPP_PHONE_ID", "")     # Phone number ID
    WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "shivani_verify_123")

    # Meta API base
    META_API_VERSION: str = os.getenv("META_API_VERSION", "v19.0")
    META_API_BASE: str = f"https://graph.facebook.com/{META_API_VERSION}"

    # Support mobile shown to drivers in messages
    SUPPORT_MOBILE: str = os.getenv("SUPPORT_MOBILE", "+91-XXXXXXXXXX")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./shivani_tracking.db")

    # Follow-up interval in seconds (6 hours = 21600)
    FOLLOWUP_INTERVAL_SECONDS: int = int(os.getenv("FOLLOWUP_INTERVAL_SECONDS", "21600"))

    # Scheduler poll interval (how often to check for due follow-ups)
    SCHEDULER_POLL_SECONDS: int = int(os.getenv("SCHEDULER_POLL_SECONDS", "60"))


settings = Settings()
