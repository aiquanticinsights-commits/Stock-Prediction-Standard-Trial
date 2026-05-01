"""
Forex PIP and currency-pair correlation utilities.

This module helps with:
1) PIP calculations (size, move in pips, pip value)
2) Correlation analysis between FX pairs and other assets
   (e.g., USD/JPY vs S&P 500 returns)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import pandas as pd

try:
    import yfinance as yf  # type: ignore
except ImportError:
    yf = None  # type: ignore


CorrelationMethod = Literal["pearson", "spearman", "kendall"]


@dataclass(frozen=True)
class CorrelationResult:
    pair_symbol: str
    asset_symbol: str
    method: CorrelationMethod
    lag_periods: int
    observations: int
    correlation: float


def normalize_fx_symbol(symbol: str) -> str:
    """
    Convert common pair formats to a canonical 6-letter form.
    Examples:
    - USD/JPY -> USDJPY
    - EUR_USD -> EURUSD
    - gbpusd -> GBPUSD
    """
    cleaned = symbol.replace("/", "").replace("_", "").strip().upper()
    if len(cleaned) != 6:
        raise ValueError(f"Unsupported FX pair format: {symbol}")
    return cleaned


def pip_size(symbol: str) -> float:
    """
    Return pip size for a forex pair.
    - JPY quote pairs use 0.01
    - Most others use 0.0001
    """
    pair = normalize_fx_symbol(symbol)
    quote = pair[3:]
    return 0.01 if quote == "JPY" else 0.0001


def pips_moved(symbol: str, open_price: float, close_price: float) -> float:
    """
    Calculate move in pips between two prices.
    Positive = moved up, Negative = moved down.
    """
    size = pip_size(symbol)
    return (float(close_price) - float(open_price)) / size


def pip_value(
    symbol: str,
    *,
    lot_size: int = 100_000,
    account_currency: Optional[str] = None,
    quote_to_account_rate: float = 1.0,
) -> float:
    """
    Estimate pip value in account currency.

    For standard forex:
      pip_value_in_quote = pip_size * lot_size

    If account currency differs from quote currency, provide
    `quote_to_account_rate` to convert quote -> account.
    """
    pair = normalize_fx_symbol(symbol)
    quote = pair[3:]
    value_in_quote = pip_size(pair) * float(lot_size)

    if account_currency is None or account_currency.upper() == quote:
        return value_in_quote

    if quote_to_account_rate <= 0:
        raise ValueError("quote_to_account_rate must be positive.")
    return value_in_quote * float(quote_to_account_rate)


def _returns_from_close(df: pd.DataFrame, close_col: str) -> pd.Series:
    if close_col not in df.columns:
        raise ValueError(f"Missing close column: {close_col}")
    close = pd.to_numeric(df[close_col], errors="coerce")
    return close.pct_change().dropna()


def pair_asset_correlation(
    pair_df: pd.DataFrame,
    asset_df: pd.DataFrame,
    *,
    pair_symbol: str = "FX_PAIR",
    asset_symbol: str = "ASSET",
    pair_close_col: str = "close",
    asset_close_col: str = "close",
    method: CorrelationMethod = "pearson",
    lag_periods: int = 0,
) -> CorrelationResult:
    """
    Correlate FX pair returns with another asset's returns.

    Args:
        lag_periods:
            Positive lag means FX returns are shifted forward before matching,
            useful for checking whether FX moves lead the other asset.
    """
    pair_ret = _returns_from_close(pair_df, pair_close_col)
    asset_ret = _returns_from_close(asset_df, asset_close_col)

    if lag_periods != 0:
        pair_ret = pair_ret.shift(lag_periods)

    aligned = pd.concat([pair_ret.rename("pair"), asset_ret.rename("asset")], axis=1).dropna()
    if aligned.empty:
        corr = 0.0
        obs = 0
    else:
        corr = float(aligned["pair"].corr(aligned["asset"], method=method))
        obs = int(len(aligned))

    return CorrelationResult(
        pair_symbol=pair_symbol,
        asset_symbol=asset_symbol,
        method=method,
        lag_periods=lag_periods,
        observations=obs,
        correlation=corr,
    )


def rolling_pair_asset_correlation(
    pair_df: pd.DataFrame,
    asset_df: pd.DataFrame,
    *,
    pair_close_col: str = "close",
    asset_close_col: str = "close",
    window: int = 20,
    method: CorrelationMethod = "pearson",
) -> pd.Series:
    """
    Rolling correlation of FX returns and asset returns.
    """
    if window < 2:
        raise ValueError("window must be >= 2")

    pair_ret = _returns_from_close(pair_df, pair_close_col)
    asset_ret = _returns_from_close(asset_df, asset_close_col)
    aligned = pd.concat([pair_ret.rename("pair"), asset_ret.rename("asset")], axis=1).dropna()

    if aligned.empty:
        return pd.Series(dtype=float, name="rolling_correlation")

    series = aligned["pair"].rolling(window=window).corr(aligned["asset"], method=method)
    series.name = "rolling_correlation"
    return series


def fetch_sp500_and_usdjpy(
    *,
    start: str,
    end: str,
    interval: str = "1d",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Convenience helper using yfinance for:
    - USD/JPY via ticker 'JPY=X'
    - S&P 500 via ticker '^GSPC'
    """
    if yf is None:
        raise ImportError("yfinance is not installed. Run: pip install yfinance")

    usdjpy = yf.download("JPY=X", start=start, end=end, interval=interval, progress=False)
    spx = yf.download("^GSPC", start=start, end=end, interval=interval, progress=False)

    if usdjpy.empty or spx.empty:
        return (
            pd.DataFrame(columns=["close"]),
            pd.DataFrame(columns=["close"]),
        )

    usdjpy = usdjpy.rename(columns={"Close": "close"})[["close"]]
    spx = spx.rename(columns={"Close": "close"})[["close"]]
    return usdjpy, spx


if __name__ == "__main__":
    # Example: does USD/JPY co-move with S&P 500?
    pair_df, spx_df = fetch_sp500_and_usdjpy(start="2024-01-01", end="2025-01-01", interval="1d")
    result = pair_asset_correlation(
        pair_df,
        spx_df,
        pair_symbol="USD/JPY",
        asset_symbol="S&P500",
        method="pearson",
    )
    print(result)
