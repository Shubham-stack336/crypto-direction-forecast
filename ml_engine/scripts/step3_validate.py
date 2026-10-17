import pandas as pd

CSV_PATH = "data/raw/btc_usdt_1h.csv"
EXPECTED_GAP = pd.Timedelta(hours=1)
MIN_ROWS = 500
NUMERIC_COLS = ["open", "high", "low", "close", "volume"]


def load_csv(path):
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def validate(df, min_rows=MIN_ROWS):


    problems = []

    df = df.sort_values("timestamp")
    df = df.drop_duplicates(subset="timestamp", keep="last")
    df = df.reset_index(drop=True)

    for col in NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    missing = int(df[NUMERIC_COLS].isna().sum().sum())
    if missing > 0:
        problems.append(f"{missing} missing/non-numeric values")

    if (df[["open", "high", "low", "close"]] <= 0).any().any():
        problems.append("Found zero or negative prices")

    if (df["volume"] < 0).any():
        problems.append("Found negative volume")

    high_bad = df["high"] < df[["open", "close", "low"]].max(axis=1)
    low_bad = df["low"] > df[["open", "close", "high"]].min(axis=1)
    bad_candles = int((high_bad | low_bad).sum())
    if bad_candles > 0:
        problems.append(f"{bad_candles} candles with impossible high/low")

    gaps = df["timestamp"].diff().dropna()
    gaps = gaps[gaps != EXPECTED_GAP]
    if len(gaps) > 0:
        problems.append(f"{len(gaps)} timestamp gaps, largest: {gaps.max()}")

    if len(df) < min_rows:
        problems.append(f"Only {len(df)} rows, need at least {min_rows}")

    return df, problems


if __name__ == "__main__":
    df = load_csv(CSV_PATH)
    clean_df, problems = validate(df)

    print(f"Rows: {len(clean_df)}")
    print(f"From {clean_df['timestamp'].iloc[0]} to {clean_df['timestamp'].iloc[-1]}")

    if problems:
        print("PROBLEMS FOUND:")
        for p in problems:
            print(" -", p)
    else:
        print("Data validation passed.")
