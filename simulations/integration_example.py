"""
Integration example:
1) Fetch standardized market data from UniversalDataLoader
2) Run volatility_report with market-aware annualization
"""

from data_ingestion import OandaConfig, UniversalDataLoader
from simulations import volatility_report


def stock_example() -> None:
    loader = UniversalDataLoader()
    df = loader.load(
        asset_class="stock",
        symbol="AAPL",
        interval="1d",
        start="2025-01-01",
    )
    report = volatility_report(df, asset_class="stock", interval="1d")
    print("Stock report:")
    print(report)


def crypto_example() -> None:
    loader = UniversalDataLoader(crypto_exchange="binance")
    df = loader.load(
        asset_class="crypto",
        symbol="BTC/USDT",
        interval="1h",
        limit=1000,
    )
    report = volatility_report(df, asset_class="crypto", interval="1h")
    print("Crypto report:")
    print(report)


def forex_example() -> None:
    # Replace placeholders with your real OANDA credentials.
    oanda = OandaConfig(
        api_key="YOUR_OANDA_API_KEY",
        account_id="YOUR_OANDA_ACCOUNT_ID",
        environment="practice",
    )
    loader = UniversalDataLoader(oanda_config=oanda)
    df = loader.load(
        asset_class="forex",
        symbol="EUR_USD",
        interval="1h",
        limit=500,
    )
    report = volatility_report(df, asset_class="forex", interval="1h")
    print("Forex report:")
    print(report)


if __name__ == "__main__":
    # Run whichever examples you need.
    stock_example()
    # crypto_example()
    # forex_example()
