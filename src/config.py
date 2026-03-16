import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    FRED_API_KEY: str = os.getenv("FRED_API_KEY", "")
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    SEC_USER_AGENT: str = "StockAnalyst/1.0 (stock-analyst-project@example.com)"
    SEC_REQUEST_DELAY: float = 0.1
    FRED_SERIES: dict = {
        "fed_funds_rate": "FEDFUNDS",
        "gdp": "GDPC1",
        "unemployment": "UNRATE",
        "cpi": "CPIAUCSL",
        "yield_spread": "T10Y2Y",
    }


settings = Settings()
