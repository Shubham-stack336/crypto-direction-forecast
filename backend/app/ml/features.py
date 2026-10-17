"""Feature pipeline v1. Uses only information available at each candle's close."""
import pandas as pd

FEATURE_VERSION = "v1"
FEATURE_COLUMNS = [
    "ret_1",
    "ret_2",
    "ret_3",
    "sma_ratio_10",
    "sma_ratio_30",
    "vol_10",
    "volume_change_1",
]
WARMUP_ROWS = 30


def make_features(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame({"timestamp": df["timestamp"]}, index=df.index)

    ret = df["close"].pct_change()
    out["ret_1"] = ret
    out["ret_2"] = ret.shift(1)
    out["ret_3"] = ret.shift(2)

    out["sma_ratio_10"] = df["close"] / df["close"].rolling(10).mean() - 1
    out["sma_ratio_30"] = df["close"] / df["close"].rolling(30).mean() - 1

    out["vol_10"] = ret.rolling(10).std()
    out["volume_change_1"] = df["volume"].pct_change()

    return out.dropna()
