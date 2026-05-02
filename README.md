# Stock-Prediction-Standard-Trial

Multi-asset data pipeline starter for AI/ML experiments across:

- Stocks (`yfinance`)
- Crypto (`ccxt`)
- Forex (`OANDA`)

The repository includes unified data ingestion, volatility utilities, and FX PIP/correlation helpers.

## Features

- Universal loader that normalizes OHLCV market data into one schema
- Volatility checks with crypto-aware 24/7 annualization logic
- Forex PIP calculations and cross-asset correlation tools
- MIT licensed for open use and modification

## Project Structure

```text
├── data_ingestion/       # Unified loaders for Stocks, Crypto, and Forex
├── deep_learning/        # TFT, N-BEATS, and Informer architectures
├── rl_agents/            # Stable-Baselines3 PPO/DQN environments
├── sentiment_analysis/   # LLM agents for news and social scraping
├── simulations/          # Monte Carlo, GARCH, and Black-Litterman
├── config/               # Global settings for tickers and API keys
├── requirements.txt      # 2026 dependency stack
└── main.py               # Central execution script
```

## Standardized Data Format

All loaders return a `pandas.DataFrame` with:

- `timestamp`
- `symbol`
- `asset_class`
- `source`
- `interval`
- `open`
- `high`
- `low`
- `close`
- `volume`

## Installation

Use **Python 3.11+** (required for `pandas` 3.x in `requirements.txt`).

```bash
pip install pandas numpy requests yfinance ccxt
```

## Quick Start

```python
from data_ingestion import UniversalDataLoader
from simulations import volatility_report

loader = UniversalDataLoader()

df = loader.load(
    asset_class="stock",
    symbol="AAPL",
    interval="1d",
    start="2025-01-01",
)

report = volatility_report(df, asset_class="stock", interval="1d")
print(report)
```

## Forex PIP + Correlation Example

```python
from data_ingestion import (
    fetch_sp500_and_usdjpy,
    pair_asset_correlation,
    pips_moved,
)

# PIP movement example
print(pips_moved("USD/JPY", 155.10, 155.85))

# USD/JPY vs S&P 500 correlation
pair_df, spx_df = fetch_sp500_and_usdjpy(
    start="2024-01-01",
    end="2025-01-01",
    interval="1d",
)
result = pair_asset_correlation(
    pair_df,
    spx_df,
    pair_symbol="USD/JPY",
    asset_symbol="S&P500",
)
print(result)
```

## OANDA Setup

For forex ingestion via OANDA, create config with your credentials:

```python
from data_ingestion import OandaConfig, UniversalDataLoader

oanda = OandaConfig(
    api_key="YOUR_OANDA_API_KEY",
    account_id="YOUR_OANDA_ACCOUNT_ID",
    environment="practice",  # or "live"
)

loader = UniversalDataLoader(oanda_config=oanda)
```

## License

This project is licensed under the MIT License. See `LICENSE`.
