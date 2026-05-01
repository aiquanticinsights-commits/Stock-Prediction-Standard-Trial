"""
Global project settings for symbols, APIs, and runtime defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class GlobalSettings:
    stock_tickers: list[str] = field(default_factory=lambda: ["AAPL", "MSFT", "SPY"])
    crypto_pairs: list[str] = field(default_factory=lambda: ["BTC/USDT", "ETH/USDT"])
    forex_pairs: list[str] = field(default_factory=lambda: ["EUR_USD", "USD_JPY", "GBP_USD"])

    default_stock_interval: str = "1d"
    default_crypto_interval: str = "1h"
    default_forex_interval: str = "1h"

    # API keys are sourced from environment variables by default.
    oanda_api_key: str = field(default_factory=lambda: os.getenv("OANDA_API_KEY", ""))
    oanda_account_id: str = field(default_factory=lambda: os.getenv("OANDA_ACCOUNT_ID", ""))
    oanda_environment: str = field(default_factory=lambda: os.getenv("OANDA_ENV", "practice"))


settings = GlobalSettings()
