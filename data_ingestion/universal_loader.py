"""
Universal market data loader for multi-asset AI models.

Supported sources:
- Stocks: yfinance
- Crypto: ccxt
- Forex: OANDA REST API

All returned data is normalized into a single schema:
[
    "timestamp", "symbol", "asset_class", "source", "interval",
    "open", "high", "low", "close", "volume"
]
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Optional

import pandas as pd
import requests

try:
    import ccxt  # type: ignore
except ImportError:
    ccxt = None  # type: ignore

try:
    import yfinance as yf  # type: ignore
except ImportError:
    yf = None  # type: ignore


AssetClass = Literal["stock", "crypto", "forex"]


@dataclass(frozen=True)
class OandaConfig:
    api_key: str
    account_id: str
    environment: Literal["practice", "live"] = "practice"

    @property
    def base_url(self) -> str:
        if self.environment == "live":
            return "https://api-fxtrade.oanda.com/v3"
        return "https://api-fxpractice.oanda.com/v3"


class UniversalDataLoader:
    """Fetch and standardize market data across multiple asset classes."""

    STANDARD_COLUMNS = [
        "timestamp",
        "symbol",
        "asset_class",
        "source",
        "interval",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    def __init__(
        self,
        *,
        crypto_exchange: str = "binance",
        oanda_config: Optional[OandaConfig] = None,
    ) -> None:
        self.crypto_exchange = crypto_exchange
        self.oanda_config = oanda_config
        self._exchange = None

    def load(
        self,
        *,
        asset_class: AssetClass,
        symbol: str,
        interval: str = "1h",
        start: Optional[str | datetime] = None,
        end: Optional[str | datetime] = None,
        limit: int = 500,
    ) -> pd.DataFrame:
        """
        Load historical OHLCV data and normalize to a common schema.

        Parameters:
            asset_class: "stock", "crypto", or "forex"
            symbol: Provider symbol (e.g., AAPL, BTC/USDT, EUR_USD)
            interval: Timeframe (e.g., 1m, 5m, 1h, 1d)
            start: Start datetime (ISO str or datetime)
            end: End datetime (ISO str or datetime)
            limit: Max rows when provider supports bounded requests
        """
        if asset_class == "stock":
            raw = self._fetch_stocks(symbol=symbol, interval=interval, start=start, end=end)
            return self._standardize(
                raw,
                symbol=symbol,
                asset_class="stock",
                source="yfinance",
                interval=interval,
            )

        if asset_class == "crypto":
            raw = self._fetch_crypto(
                symbol=symbol,
                interval=interval,
                start=start,
                end=end,
                limit=limit,
            )
            return self._standardize(
                raw,
                symbol=symbol,
                asset_class="crypto",
                source=f"ccxt:{self.crypto_exchange}",
                interval=interval,
            )

        if asset_class == "forex":
            raw = self._fetch_forex(
                symbol=symbol,
                interval=interval,
                start=start,
                end=end,
                limit=limit,
            )
            return self._standardize(
                raw,
                symbol=symbol,
                asset_class="forex",
                source="oanda",
                interval=interval,
            )

        raise ValueError(f"Unsupported asset_class: {asset_class}")

    def _fetch_stocks(
        self,
        *,
        symbol: str,
        interval: str,
        start: Optional[str | datetime],
        end: Optional[str | datetime],
    ) -> pd.DataFrame:
        if yf is None:
            raise ImportError("yfinance is not installed. Run: pip install yfinance")

        yf_interval = self._map_interval_for_yfinance(interval)
        df = yf.download(
            tickers=symbol,
            start=self._to_iso(start),
            end=self._to_iso(end),
            interval=yf_interval,
            auto_adjust=False,
            progress=False,
        )

        if df.empty:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        # yfinance index is datetime; columns are usually capitalized.
        df = df.reset_index()
        col_map = {
            "Datetime": "timestamp",
            "Date": "timestamp",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
        df = df.rename(columns=col_map)
        return df[["timestamp", "open", "high", "low", "close", "volume"]]

    def _fetch_crypto(
        self,
        *,
        symbol: str,
        interval: str,
        start: Optional[str | datetime],
        end: Optional[str | datetime],
        limit: int,
    ) -> pd.DataFrame:
        if ccxt is None:
            raise ImportError("ccxt is not installed. Run: pip install ccxt")

        exchange = self._get_exchange()
        timeframe = self._map_interval_for_ccxt(interval)
        since_ms = self._to_unix_ms(start) if start is not None else None

        ohlcv = exchange.fetch_ohlcv(symbol=symbol, timeframe=timeframe, since=since_ms, limit=limit)
        if not ohlcv:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)

        if end is not None:
            end_dt = self._to_datetime_utc(end)
            df = df[df["timestamp"] <= end_dt]

        return df

    def _fetch_forex(
        self,
        *,
        symbol: str,
        interval: str,
        start: Optional[str | datetime],
        end: Optional[str | datetime],
        limit: int,
    ) -> pd.DataFrame:
        if self.oanda_config is None:
            raise ValueError("OANDA config missing. Provide OandaConfig(api_key, account_id, ...)")

        headers = {"Authorization": f"Bearer {self.oanda_config.api_key}"}
        params: dict[str, str | int] = {
            "price": "M",
            "granularity": self._map_interval_for_oanda(interval),
            "count": max(1, min(limit, 5000)),
        }

        if start is not None:
            params["from"] = self._to_datetime_utc(start).isoformat().replace("+00:00", "Z")
        if end is not None:
            params["to"] = self._to_datetime_utc(end).isoformat().replace("+00:00", "Z")

        url = f"{self.oanda_config.base_url}/instruments/{symbol}/candles"
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()

        candles = payload.get("candles", [])
        if not candles:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        rows = []
        for c in candles:
            # Skip partial candles to keep training windows consistent.
            if not c.get("complete", False):
                continue
            mid = c.get("mid", {})
            rows.append(
                {
                    "timestamp": c.get("time"),
                    "open": float(mid.get("o", 0.0)),
                    "high": float(mid.get("h", 0.0)),
                    "low": float(mid.get("l", 0.0)),
                    "close": float(mid.get("c", 0.0)),
                    "volume": float(c.get("volume", 0.0)),
                }
            )

        return pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])

    def _standardize(
        self,
        df: pd.DataFrame,
        *,
        symbol: str,
        asset_class: AssetClass,
        source: str,
        interval: str,
    ) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=self.STANDARD_COLUMNS)

        out = df.copy()
        out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")

        numeric_cols = ["open", "high", "low", "close", "volume"]
        for col in numeric_cols:
            out[col] = pd.to_numeric(out[col], errors="coerce")

        out["symbol"] = symbol
        out["asset_class"] = asset_class
        out["source"] = source
        out["interval"] = interval

        out = out.dropna(subset=["timestamp", "open", "high", "low", "close"])
        out = out[self.STANDARD_COLUMNS].sort_values("timestamp").reset_index(drop=True)
        return out

    def _get_exchange(self):
        if self._exchange is not None:
            return self._exchange

        exchange_cls = getattr(ccxt, self.crypto_exchange, None)
        if exchange_cls is None:
            raise ValueError(f"Unknown ccxt exchange: {self.crypto_exchange}")

        self._exchange = exchange_cls({"enableRateLimit": True})
        return self._exchange

    @staticmethod
    def _to_iso(value: Optional[str | datetime]) -> Optional[str]:
        if value is None:
            return None
        return UniversalDataLoader._to_datetime_utc(value).isoformat()

    @staticmethod
    def _to_unix_ms(value: str | datetime) -> int:
        dt = UniversalDataLoader._to_datetime_utc(value)
        return int(dt.timestamp() * 1000)

    @staticmethod
    def _to_datetime_utc(value: str | datetime) -> datetime:
        if isinstance(value, datetime):
            dt = value
        else:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def _map_interval_for_yfinance(interval: str) -> str:
        mapping = {
            "1m": "1m",
            "2m": "2m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "60m": "60m",
            "90m": "90m",
            "1h": "60m",
            "1d": "1d",
            "5d": "5d",
            "1wk": "1wk",
            "1mo": "1mo",
            "3mo": "3mo",
        }
        if interval not in mapping:
            raise ValueError(f"Unsupported interval for yfinance: {interval}")
        return mapping[interval]

    @staticmethod
    def _map_interval_for_ccxt(interval: str) -> str:
        supported = {
            "1m",
            "3m",
            "5m",
            "15m",
            "30m",
            "1h",
            "2h",
            "4h",
            "6h",
            "8h",
            "12h",
            "1d",
            "3d",
            "1w",
            "1M",
        }
        if interval not in supported:
            raise ValueError(f"Unsupported interval for ccxt: {interval}")
        return interval

    @staticmethod
    def _map_interval_for_oanda(interval: str) -> str:
        mapping = {
            "5s": "S5",
            "10s": "S10",
            "15s": "S15",
            "30s": "S30",
            "1m": "M1",
            "2m": "M2",
            "4m": "M4",
            "5m": "M5",
            "10m": "M10",
            "15m": "M15",
            "30m": "M30",
            "1h": "H1",
            "2h": "H2",
            "3h": "H3",
            "4h": "H4",
            "6h": "H6",
            "8h": "H8",
            "12h": "H12",
            "1d": "D",
            "1w": "W",
            "1mo": "M",
        }
        if interval not in mapping:
            raise ValueError(f"Unsupported interval for OANDA: {interval}")
        return mapping[interval]


__all__ = ["UniversalDataLoader", "OandaConfig"]
