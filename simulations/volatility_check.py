"""
Volatility utilities with market-aware annualization.

This module handles different market schedules:
- Stocks: limited trading sessions (commonly ~252 days/year, ~6.5 hours/day)
- Crypto: 24/7 trading (365 days/year, 24 hours/day)
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd


AssetClass = Literal["stock", "crypto", "forex"]


# Typical annualized period assumptions.
PERIODS_PER_YEAR = {
    # Daily close-to-close returns.
    "stock_1d": 252,
    "crypto_1d": 365,
    "forex_1d": 252,
    # Hourly returns.
    "stock_1h": 252 * 6.5,  # Approximate regular US market hours.
    "crypto_1h": 365 * 24,  # Always-on market.
    "forex_1h": 252 * 24,   # FX is near 24/5; this is a practical simplification.
}


def _periods_per_year(asset_class: AssetClass, interval: str) -> float:
    key = f"{asset_class}_{interval}"
    if key in PERIODS_PER_YEAR:
        return float(PERIODS_PER_YEAR[key])

    # Fallback to base assumptions if interval is not explicitly mapped.
    if asset_class == "crypto":
        return 365.0
    if asset_class in {"stock", "forex"}:
        return 252.0
    raise ValueError(f"Unsupported asset_class: {asset_class}")


def calculate_log_returns(close_prices: pd.Series) -> pd.Series:
    """
    Compute log returns from a close price series.
    """
    prices = pd.to_numeric(close_prices, errors="coerce")
    prices = prices[prices > 0].dropna()
    return np.log(prices / prices.shift(1)).dropna()


def annualized_volatility(
    close_prices: pd.Series,
    *,
    asset_class: AssetClass,
    interval: str = "1d",
) -> float:
    """
    Calculate annualized volatility using market-specific periods/year.

    Returns:
        Annualized volatility as a decimal (e.g., 0.25 == 25%).
    """
    log_returns = calculate_log_returns(close_prices)
    if log_returns.empty:
        return 0.0

    periods = _periods_per_year(asset_class, interval)
    return float(log_returns.std(ddof=1) * np.sqrt(periods))


def volatility_report(
    df: pd.DataFrame,
    *,
    asset_class: AssetClass,
    interval: str = "1d",
    close_col: str = "close",
    symbol_col: str = "symbol",
) -> pd.DataFrame:
    """
    Build a per-symbol volatility report from standardized OHLCV data.

    Expected input format is compatible with `data_ingestion.universal_loader`
    output, especially `symbol` and `close` columns.
    """
    if close_col not in df.columns:
        raise ValueError(f"Missing close column: {close_col}")

    if symbol_col not in df.columns:
        # Single series fallback if symbol is absent.
        vol = annualized_volatility(df[close_col], asset_class=asset_class, interval=interval)
        return pd.DataFrame(
            [
                {
                    "symbol": "UNKNOWN",
                    "asset_class": asset_class,
                    "interval": interval,
                    "annualized_volatility": vol,
                }
            ]
        )

    rows = []
    for symbol, g in df.groupby(symbol_col):
        vol = annualized_volatility(g[close_col], asset_class=asset_class, interval=interval)
        rows.append(
            {
                "symbol": symbol,
                "asset_class": asset_class,
                "interval": interval,
                "annualized_volatility": vol,
            }
        )

    return pd.DataFrame(rows).sort_values("annualized_volatility", ascending=False).reset_index(drop=True)


if __name__ == "__main__":
    # Minimal demonstration for quick manual checks.
    sample_stock = pd.Series([100, 101, 99.5, 102, 103], name="close")
    sample_crypto = pd.Series([30000, 30300, 29850, 30750, 31200], name="close")

    print("Stock daily vol:", annualized_volatility(sample_stock, asset_class="stock", interval="1d"))
    print("Crypto daily vol:", annualized_volatility(sample_crypto, asset_class="crypto", interval="1d"))
