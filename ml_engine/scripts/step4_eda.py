import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from step3_validate import CSV_PATH, load_csv, validate

HORIZON = 3
THRESHOLD = 0.003

df, problems = validate(load_csv(CSV_PATH))
if problems:
    raise SystemExit(f"Fix data problems first: {problems}")

df["return_1h"] = df["close"].pct_change()
print("Hourly return summary:")
print(df["return_1h"].describe())
print(f"Hourly volatility (std): {df['return_1h'].std():.5f}")

df["forward_return"] = df["close"].shift(-HORIZON) / df["close"] - 1
valid = df.dropna(subset=["forward_return"]).copy()
valid["label"] = np.select(
    [valid["forward_return"] > THRESHOLD, valid["forward_return"] < -THRESHOLD],
    ["UP", "DOWN"],
    default="SIDEWAYS",
)

print(f"\nLabeled rows: {len(valid)} (dropped last {HORIZON} rows with no future)")
print(valid["label"].value_counts())
print((valid["label"].value_counts(normalize=True) * 100).round(1))

plt.hist(df["return_1h"].dropna(), bins=60)
plt.title("BTC/USDT 1h returns")
plt.xlabel("return")
plt.ylabel("count")
plt.savefig("data/return_hist.png")
print("Chart saved to data/return_hist.png")
