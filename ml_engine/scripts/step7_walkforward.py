import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from dataset import HORIZON, build_dataset
from features import FEATURE_COLUMNS

N_FOLDS = 5

data = build_dataset()
dev = data.iloc[: int(len(data) * 0.85)]
fold_size = len(dev) // (N_FOLDS + 1)


def make_logreg():
    return make_pipeline(
        StandardScaler(),
        LogisticRegression(class_weight="balanced", max_iter=1000),
    )


naive_scores, lr_scores, lr_f1s = [], [], []

for k in range(1, N_FOLDS + 1):
    train_end = fold_size * k
    train = dev.iloc[: train_end - HORIZON]
    test = dev.iloc[train_end : train_end + fold_size]

    X_train, y_train = train[FEATURE_COLUMNS], train["label"]
    X_test, y_test = test[FEATURE_COLUMNS], test["label"]

    naive = DummyClassifier(strategy="most_frequent").fit(X_train, y_train)
    logreg = make_logreg().fit(X_train, y_train)

    naive_bal = balanced_accuracy_score(y_test, naive.predict(X_test))
    lr_pred = logreg.predict(X_test)
    lr_bal = balanced_accuracy_score(y_test, lr_pred)
    lr_f1 = f1_score(y_test, lr_pred, average="macro", zero_division=0)

    naive_scores.append(naive_bal)
    lr_scores.append(lr_bal)
    lr_f1s.append(lr_f1)

    print(
        f"Fold {k}: train={len(train)}, test={len(test)} "
        f"({test['timestamp'].iloc[0].date()} -> {test['timestamp'].iloc[-1].date()}) "
        f"naive_bal={naive_bal:.3f}  logreg_bal={lr_bal:.3f}  logreg_macroF1={lr_f1:.3f}"
    )

print(f"\nNaive  balanced acc: mean={np.mean(naive_scores):.3f}")
print(f"LogReg balanced acc: mean={np.mean(lr_scores):.3f}, std={np.std(lr_scores):.3f}")
print(f"LogReg macro F1:     mean={np.mean(lr_f1s):.3f}, std={np.std(lr_f1s):.3f}")
wins = sum(1 for a, b in zip(lr_scores, naive_scores) if a > b)
print(f"LogReg beat naive in {wins} of {N_FOLDS} folds")