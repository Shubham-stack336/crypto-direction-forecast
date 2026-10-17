import pandas as pd

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


def make_features(df):
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


FEATURE_COLUMNS_V2 = FEATURE_COLUMNS + [
    "rsi_14",
    "macd_hist",
    "bb_pos_20",
    "bb_width_20",
    "volume_ratio_20",
]
WARMUP_ROWS_V2 = 100


def make_features_v2(df):
    base = make_features(df)
    close = df["close"]
    extra = pd.DataFrame(index=df.index)

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    extra["rsi_14"] = 100 - 100 / (1 + avg_gain / avg_loss)

    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=9, adjust=False).mean()
    extra["macd_hist"] = (macd - signal) / close

    mid = close.rolling(20).mean()
    spread = close.rolling(20).std()
    extra["bb_pos_20"] = (close - mid) / (2 * spread)
    extra["bb_width_20"] = 4 * spread / mid

    extra["volume_ratio_20"] = df["volume"] / df["volume"].rolling(20).mean() - 1

    out = base.join(extra).dropna()
    return out[out.index >= WARMUP_ROWS_V2]
