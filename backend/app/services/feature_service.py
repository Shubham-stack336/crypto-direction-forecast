"""Feature Service Layer.

Computes technical indicators and creates target labels with strict temporal hygiene:
- Zero data leakage (past and present only for features)
- Target is strictly next day's direction (Close_{t+1} > Close_t)
- Features include returns, moving averages, RSI, volatility, and volume momentum.
"""

import logging
from typing import Tuple
import numpy as np
import pandas as pd

logger = logging.getLogger("app.service.features")

FEATURE_NAMES = [
    "return_1d",
    "return_3d",
    "return_7d",
    "sma_7_ratio",
    "sma_14_ratio",
    "sma_30_ratio",
    "rsi_14",
    "volatility_7d",
    "volatility_14d",
    "volume_ratio_7d",
]


class FeatureService:
    @staticmethod
    def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """Calculate the Relative Strength Index (RSI) using Wilder's smoothing."""
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

        rs = avg_gain / (avg_loss + 1e-9)
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    def generate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate indicator features strictly using t <= present information.

        Does not create target or drop rows.
        """
        feats = pd.DataFrame(index=df.index)
        close = df["close"]
        volume = df["volume"]

        # Returns over multiple horizons
        feats["return_1d"] = close.pct_change(1)
        feats["return_3d"] = close.pct_change(3)
        feats["return_7d"] = close.pct_change(7)

        # Moving Averages (price relative to SMA)
        sma_7 = close.rolling(window=7).mean()
        sma_14 = close.rolling(window=14).mean()
        sma_30 = close.rolling(window=30).mean()

        feats["sma_7_ratio"] = close / (sma_7 + 1e-9) - 1.0
        feats["sma_14_ratio"] = close / (sma_14 + 1e-9) - 1.0
        feats["sma_30_ratio"] = close / (sma_30 + 1e-9) - 1.0

        # Momentum: RSI (14-day)
        feats["rsi_14"] = self.calculate_rsi(close, period=14)

        # Volatility: rolling std dev of 1-day returns
        daily_ret = feats["return_1d"]
        feats["volatility_7d"] = daily_ret.rolling(window=7).std()
        feats["volatility_14d"] = daily_ret.rolling(window=14).std()

        # Volume momentum: volume relative to 7-day average
        vol_mean_7 = volume.rolling(window=7).mean()
        feats["volume_ratio_7d"] = volume / (vol_mean_7 + 1e-9) - 1.0

        return feats[FEATURE_NAMES]

    def build_dataset(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build full dataset with features and strictly forward target.

        Target: 1 if Close_{t+1} > Close_t else 0.
        Drops NaN warmup periods and drops the final row where tomorrow's outcome is unknown.
        """
        feats = self.generate_features(df)
        dataset = feats.copy()

        # Target is next-day direction (shifted backwards so row t has target of t+1)
        next_close = df["close"].shift(-1)
        target = (next_close > df["close"]).astype(float)
        
        # When next_close is NaN (the very last day), target is NaN
        target[next_close.isna()] = np.nan
        dataset["target"] = target
        dataset["close"] = df["close"]

        # Drop initial rolling warmup NaNs and the last row where target is unknown
        cleaned = dataset.dropna().copy()
        cleaned["target"] = cleaned["target"].astype(int)

        logger.info(
            f"Built dataset: {len(cleaned)} valid samples with {len(FEATURE_NAMES)} features. "
            f"Class distribution: {cleaned['target'].value_counts().to_dict()}"
        )
        return cleaned

    def get_latest_inference_features(self, df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
        """Extract features for the most recent closed candle to predict tomorrow."""
        feats = self.generate_features(df)
        latest_row = feats.iloc[[-1]].copy()
        
        # Check if latest row has any NaNs
        if latest_row.isna().any().any():
            raise ValueError("Insufficient history to calculate all indicator features for inference")

        latest_meta = {
            "date": str(df.index[-1].date()) if hasattr(df.index[-1], "date") else str(df.index[-1]),
            "close": float(df["close"].iloc[-1]),
            "rsi_14": float(latest_row["rsi_14"].iloc[0]),
            "return_1d_pct": float(latest_row["return_1d"].iloc[0] * 100),
            "volatility_7d": float(latest_row["volatility_7d"].iloc[0]),
        }
        return latest_row[FEATURE_NAMES], latest_meta
