import numpy as np
import pandas as pd


def make_target(df, horizon=3, threshold=0.003):
    forward_return = df["close"].shift(-horizon) / df["close"] - 1

    label = pd.Series(
        np.select(
            [forward_return > threshold, forward_return < -threshold],
            ["UP", "DOWN"],
            default="SIDEWAYS",
        ),
        index=df.index,
    ).where(forward_return.notna())

    out = pd.DataFrame(
        {"timestamp": df["timestamp"], "forward_return": forward_return, "label": label}
    )
    return out.dropna()
