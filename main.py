"""
Central execution script for multi-asset workflows.
"""

from __future__ import annotations

import argparse

from config import settings
from data_ingestion import OandaConfig, UniversalDataLoader


def build_loader() -> UniversalDataLoader:
    if settings.oanda_api_key and settings.oanda_account_id:
        oanda_config = OandaConfig(
            api_key=settings.oanda_api_key,
            account_id=settings.oanda_account_id,
            environment="live" if settings.oanda_environment == "live" else "practice",
        )
        return UniversalDataLoader(oanda_config=oanda_config)
    return UniversalDataLoader()


def run_ingest_sample() -> None:
    loader = build_loader()
    df = loader.load(
        asset_class="stock",
        symbol=settings.stock_tickers[0],
        interval=settings.default_stock_interval,
        start="2025-01-01",
    )
    print(df.tail(5))


def main() -> None:
    parser = argparse.ArgumentParser(description="Stock-Prediction-Standard-Trial runner")
    parser.add_argument(
        "--task",
        choices=["ingest_sample"],
        default="ingest_sample",
        help="Task to run",
    )
    args = parser.parse_args()

    if args.task == "ingest_sample":
        run_ingest_sample()


if __name__ == "__main__":
    main()
