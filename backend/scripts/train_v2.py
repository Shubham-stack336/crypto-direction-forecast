"""Model v2 with rules fixed before the holdout was looked at.

Development: 25 coins, before 2026-08-07 (the same data the current models learned from).
Selection:   lowest log loss on three walk-forward folds of the development data.
Holdout:     2023-11-01 to 2024-10-10, 14 coins. Earlier than every training period, so neither the
             current models nor v2 saw it, and it was never used to choose anything.
Accept v2 only if on the holdout
  1. log loss is lower than the current models' and than the class-frequency baseline,
  2. the calibration error is lower than the current models',
  3. balanced accuracy is at most 0.005 below the current models'.
The holdout is evaluated once. The old 2026-08 to 2026-11 test period is not touched.

Run from backend/:  python scripts/train_v2.py download | select | final
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BACKEND), str(Path(__file__).resolve().parent)]

import ccxt
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, log_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.ml import features as v1
from app.ml import features_v2 as v2
from app.ml.validation import validate
from train_real_models import ARTIFACTS_DIR, CLASSES, HORIZON, THRESHOLD, TIMEFRAME, fetch_page
from train_universal_model import CACHE_DIR, TRAIN_COINS

HOLDOUT_COINS = ["BTC", "ETH", "SOL", "DOGE", "XRP", "LINK", "ADA", "INJ", "PEPE", "SHIB", "AAVE", "VET", "FET", "GRT"]
HOLDOUT = (pd.Timestamp("2023-11-01", tz="UTC"), pd.Timestamp("2024-10-10", tz="UTC"))
DEV_END = pd.Timestamp("2026-08-07 04:00", tz="UTC")
HOLDOUT_DIR = BACKEND / "data" / "universe" / "holdout"
CANDIDATE = BACKEND / "data" / "v2_candidate.json"
GAP = pd.Timedelta(hours=24)
EVERY = 3  # labels look three hours ahead, so neighbouring rows overlap
CLEAR_SHARE = 0.2  # the 20% most confident development forecasts count as "clear"


def download():
    HOLDOUT_DIR.mkdir(parents=True, exist_ok=True)
    exchange = ccxt.binance({"enableRateLimit": True, "timeout": 60000, "options": {"fetchMarkets": {"types": ["spot"]}}})
    for coin in HOLDOUT_COINS:
        path = HOLDOUT_DIR / f"{coin.lower()}.csv"
        if path.exists():
            continue
        since, end, rows = int(HOLDOUT[0].timestamp() * 1000), int(HOLDOUT[1].timestamp() * 1000), []
        while since < end:
            page = fetch_page(exchange, f"{coin}/USDT", since)
            if not page:
                break
            rows += page
            since = page[-1][0] + 3_600_000
        df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df = df[df["timestamp"] < end]
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.to_csv(path, index=False)
        print(coin, len(df), flush=True)


def dataset(path, coin):
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df, problems = validate(df)
    if problems:
        raise ValueError(f"{coin}: {problems}")
    forward = df["close"].shift(-HORIZON) / df["close"] - 1
    label = np.select([forward > THRESHOLD, forward < -THRESHOLD], ["UP", "DOWN"], default="SIDEWAYS")
    data = v2.make_features(df).assign(coin=coin)
    old = v1.make_features(df).drop(columns="timestamp").add_prefix("v1_")
    data = data.join(old, how="inner").join(pd.DataFrame({"label": label, "known": forward.notna()}))
    data = data[data["known"]].drop(columns="known")
    numeric = data.drop(columns=["timestamp", "coin", "label"]).to_numpy(dtype=float)
    return data[np.isfinite(numeric).all(axis=1)].iloc[::EVERY]


def development():
    data = pd.concat([dataset(CACHE_DIR / f"{c.lower()}_usdt_1h.csv", c) for c in TRAIN_COINS], ignore_index=True)
    return data[data["timestamp"] < DEV_END].sort_values("timestamp", ignore_index=True)


V1 = [f"v1_{c}" for c in v1.FEATURE_COLUMNS]
V2 = v2.FEATURE_COLUMNS


def candidates():
    def boost(**kw):
        return HistGradientBoostingClassifier(random_state=42, early_stopping=False, **kw)

    return {
        "current_recipe_rf_balanced": (V1, RandomForestClassifier(
            n_estimators=300, max_depth=5, min_samples_leaf=50, class_weight="balanced_subsample",
            random_state=42, n_jobs=-1)),
        "boosting_v1_features": (V1, boost(max_iter=150, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=200)),
        "boosting_v2_small": (V2, boost(max_iter=150, learning_rate=0.05, max_leaf_nodes=8, min_samples_leaf=400)),
        "boosting_v2_medium": (V2, boost(max_iter=200, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=400)),
        "forest_v2": (V2, RandomForestClassifier(
            n_estimators=200, max_depth=9, min_samples_leaf=100, random_state=42, n_jobs=-1)),
        "logistic_v2": (V2, make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))),
    }


def ece(y, proba, bins=10):
    """Average gap between the probability shown and how often that class happened."""
    total = 0.0
    for k, name in enumerate(CLASSES):
        p, hit = proba[:, k], (y == name).astype(float)
        which = np.minimum((p * bins).astype(int), bins - 1)
        for b in range(bins):
            inside = which == b
            if inside.any():
                total += inside.mean() * abs(p[inside].mean() - hit[inside].mean())
    return total / len(CLASSES)


def score(y, proba):
    y = np.asarray(y, dtype=object)
    pred = np.array(CLASSES, dtype=object)[proba.argmax(axis=1)]
    moved = np.isin(y, ["UP", "DOWN"]) & np.isin(pred, ["UP", "DOWN"])
    return {
        "log_loss": float(log_loss(y.astype(str), proba, labels=CLASSES)),
        "calibration_error": float(ece(y, proba)),
        "balanced_accuracy": float(balanced_accuracy_score(y.astype(str), pred.astype(str))),
        "accuracy": float((pred == y).mean()),
        "directional_hit_rate": float((pred[moved] == y[moved]).mean()) if moved.any() else None,
        "macro_f1": float(sklearn.metrics.f1_score(y.astype(str), pred.astype(str), average="macro")),
    }


def folds(data):
    times = data["timestamp"]
    start, end = times.min(), times.max()
    for k in range(3):
        a, b = (start + (end - start) * f for f in (0.4 + 0.2 * k, 0.6 + 0.2 * k))
        yield times < a - GAP, (times >= a) & (times < b)


def select():
    data = development()
    print("development rows", len(data), dict(data["label"].value_counts(normalize=True).round(3)), flush=True)
    report, oof = {}, {}
    for name, (cols, model) in candidates().items():
        parts = []
        for train, valid in folds(data):
            model.fit(data.loc[train, cols].to_numpy(), data.loc[train, "label"])
            parts.append((data.loc[valid, "label"].to_numpy(), model.predict_proba(data.loc[valid, cols].to_numpy())))
        y, proba = np.concatenate([p[0] for p in parts]), np.concatenate([p[1] for p in parts])
        report[name], oof[name] = score(y, proba), proba
        print(f"{name:28s}", {k: round(v, 4) for k, v in report[name].items()}, flush=True)
    best = min((n for n in report if not n.startswith("current")), key=lambda n: report[n]["log_loss"])
    clear = float(np.quantile(oof[best].max(axis=1), 1 - CLEAR_SHARE))
    CANDIDATE.write_text(json.dumps({"best": best, "clear_threshold": clear, "cv": report}, indent=2))
    print("selected", best, "clear threshold", round(clear, 4))


def final():
    chosen = json.loads(CANDIDATE.read_text())
    cols, model = candidates()[chosen["best"]]
    data = development()
    model.fit(data[cols].to_numpy(), data["label"])
    hold = pd.concat([dataset(HOLDOUT_DIR / f"{c.lower()}.csv", c) for c in HOLDOUT_COINS], ignore_index=True)
    y = hold["label"].to_numpy()
    new = model.predict_proba(hold[cols].to_numpy())

    old = np.zeros_like(new)  # exactly what the API serves today, coin by coin
    for coin, rows in hold.groupby("coin"):
        own = ARTIFACTS_DIR / f"{coin.lower()}_usdt_1h_rf.joblib"
        artifact = joblib.load(own if own.exists() else ARTIFACTS_DIR / "all_usdt_1h_rf.joblib")["model"]
        X = rows[V1].set_axis(v1.FEATURE_COLUMNS, axis=1)
        old[rows.index] = artifact.predict_proba(X)
    freq = data["label"].value_counts(normalize=True)[CLASSES].to_numpy()
    results = {
        "model_v2": score(y, new),
        "current_models": score(y, old),
        "naive_class_frequency": score(y, np.tile(freq, (len(y), 1))),
    }
    groups = {}
    for title, coins in (("own_model_coins", ["BTC", "ETH", "SOL", "DOGE"]),
                         ("never_trained_coins", ["PEPE", "SHIB", "AAVE", "VET", "FET", "GRT"])):
        m = hold["coin"].isin(coins).to_numpy()
        groups[title] = {"model_v2": score(y[m], new[m]), "current_models": score(y[m], old[m])}

    pred, top = np.array(CLASSES)[new.argmax(axis=1)], new.max(axis=1)
    bins = []
    for lo, hi in zip((0, .40, .45, .50, .55, .60, .70), (.40, .45, .50, .55, .60, .70, 1.01)):
        m = (top >= lo) & (top < hi)
        if m.sum() >= 200:
            bins.append({"from": lo, "to": min(hi, 1.0), "rows": int(m.sum()), "accuracy": float((pred[m] == y[m]).mean())})
    clear = top >= chosen["clear_threshold"]
    clear_report = {"threshold": chosen["clear_threshold"], "share": float(clear.mean()),
                    "accuracy": float((pred[clear] == y[clear]).mean()),
                    "accuracy_other": float((pred[~clear] == y[~clear]).mean()),
                    "by_label": {c: {"rows": int((clear & (pred == c)).sum()),
                                     "accuracy": float((y[clear & (pred == c)] == c).mean()) if (clear & (pred == c)).any() else None}
                                 for c in CLASSES}}
    a, b, base = results["model_v2"], results["current_models"], results["naive_class_frequency"]
    checks = {
        "log_loss_beats_current_and_baseline": a["log_loss"] < min(b["log_loss"], base["log_loss"]),
        "calibration_better": a["calibration_error"] < b["calibration_error"],
        "balanced_accuracy_kept": a["balanced_accuracy"] >= b["balanced_accuracy"] - 0.005,
    }
    print(json.dumps({"results": results, "groups": groups, "clear": clear_report, "bins": bins, "checks": checks}, indent=1))
    if hasattr(model, "n_jobs"):
        model.n_jobs = 1  # one row per request: threads only cost time
    out = BACKEND / "data" / "v2_final"
    out.mkdir(exist_ok=True)
    metadata = {
        "symbol": "ALL/USDT", "timeframe": TIMEFRAME, "horizon_candles": HORIZON, "threshold": THRESHOLD,
        "feature_version": v2.FEATURE_VERSION if cols is V2 else v1.FEATURE_VERSION,
        "feature_columns": [c.removeprefix("v1_") for c in cols], "classes": [str(c) for c in model.classes_],
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "train_period": [str(data["timestamp"].min()), str(data["timestamp"].max())],
        "sklearn_version": sklearn.__version__, "data_source": "binance via ccxt", "model_name": "universal",
        "train_coins": TRAIN_COINS, "algorithm": chosen["best"],
        "reliability": {"clear_threshold": chosen["clear_threshold"], "bins": bins},
    }
    joblib.dump({"model": model, "metadata": metadata}, out / "all_usdt_1h_rf.joblib", compress=3)
    metrics = {
        "candidate_model": "model_v2",
        "test_period": [str(hold["timestamp"].min()), str(hold["timestamp"].max())], "test_rows": len(hold),
        "test_class_distribution": {k: int(v) for k, v in hold["label"].value_counts().items()},
        "results": results, "groups": groups, "clear_signal": clear_report, "confidence_bins": bins,
        "acceptance_checks": checks, "cross_validation": chosen["cv"], "holdout_coins": HOLDOUT_COINS,
        "note": "The holdout year lies before the training period. No model saw it and it was used once. "
                "Coins are chosen among those listed today, so delisted coins are not represented.",
    }
    (out / "all_usdt_1h_rf.metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print("ACCEPTED" if all(checks.values()) else "REJECTED")


if __name__ == "__main__":
    {"download": download, "select": select, "final": final}[sys.argv[1]]()
