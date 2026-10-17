import ccxt
import pandas as pd

exchange = ccxt.binance({"enableRateLimit": True, "timeout": 10000})

raw = exchange.fetch_ohlcv("BTC/USDT", timeframe="1h", limit=5)

df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)

print(df)
print(df.dtypes)
