"""Feature pipeline v2: longer history, range-based volatility and time of day. Only past and present candles."""
import numpy as np
import pandas as pd

FEATURE_VERSION = "v2"
LONGEST_WINDOW = 168
FEATURE_COLUMNS = [
    "ret_1", "ret_2", "ret_3", "ret_6", "ret_12", "ret_24", "ret_72",
    "vol_3", "vol_10", "vol_24", "vol_72", "vol_168",
    "range_1", "range_6", "range_24",
    "sma_ratio_10", "sma_ratio_30", "sma_ratio_100",
    "rsi_14", "close_position", "position_24", "volume_ratio_24",
    "hour_sin", "hour_cos", "weekend",
]


def make_features(df: pd.DataFrame) -> pd.DataFrame:
    close, log_ret = df["close"], np.log(df["close"]).diff()
    out = pd.DataFrame({"timestamp": df["timestamp"]}, index=df.index)
    out["ret_1"], out["ret_2"], out["ret_3"] = log_ret, log_ret.shift(1), log_ret.shift(2)
    for n in (6, 12, 24, 72):
        out[f"ret_{n}"] = np.log(close / close.shift(n))
    for n in (3, 10, 24, 72, 168):
        out[f"vol_{n}"] = log_ret.rolling(n).std()
    span = np.log(df["high"] / df["low"])
    out["range_1"] = span
    for n in (6, 24):
        out[f"range_{n}"] = span.rolling(n).mean()
    for n in (10, 30, 100):
        out[f"sma_ratio_{n}"] = close / close.rolling(n).mean() - 1
    gain = log_ret.clip(lower=0).rolling(14).mean()
    loss = (-log_ret.clip(upper=0)).rolling(14).mean()
    out["rsi_14"] = (gain / (gain + loss).replace(0, np.nan)).fillna(0.5)
    out["close_position"] = ((close - df["low"]) / (df["high"] - df["low"]).replace(0, np.nan)).fillna(0.5)
    low, high = df["low"].rolling(24).min(), df["high"].rolling(24).max()
    out["position_24"] = ((close - low) / (high - low).replace(0, np.nan)).fillna(0.5)
    mean_volume = df["volume"].rolling(24).mean().replace(0, np.nan)
    out["volume_ratio_24"] = (df["volume"] / mean_volume).fillna(1.0)
    hour = 2 * np.pi * df["timestamp"].dt.hour / 24
    out["hour_sin"], out["hour_cos"] = np.sin(hour), np.cos(hour)
    out["weekend"] = (df["timestamp"].dt.dayofweek >= 5).astype(float)
    return out.iloc[LONGEST_WINDOW:].dropna()
