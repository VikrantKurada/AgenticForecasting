"""Sovereign default / credit-transition risk: gradient boosting with logistic baseline."""
import numpy as np
import pandas as pd


def fit_credit_model(features: pd.DataFrame, labels) -> dict:
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler

    y = np.asarray(labels)
    X_train, X_test, y_train, y_test = train_test_split(
        features, y, test_size=0.25, random_state=7, stratify=y
    )

    gb = GradientBoostingClassifier(random_state=7).fit(X_train, y_train)
    scaler = StandardScaler().fit(X_train)
    logistic = LogisticRegression(max_iter=1000).fit(scaler.transform(X_train), y_train)

    gb_acc = float(gb.score(X_test, y_test))
    logit_acc = float(logistic.score(scaler.transform(X_test), y_test))

    return {
        "default_probability": lambda X: [float(p) for p in gb.predict_proba(X)[:, 1]],
        "accuracy": gb_acc,
        "logistic_accuracy": logit_acc,
        "feature_importance": {
            col: float(imp) for col, imp in zip(features.columns, gb.feature_importances_)
        },
        "logistic_coefficients": {
            col: float(c) for col, c in zip(features.columns, logistic.coef_[0])
        },
        "n_train": len(X_train),
        "n_test": len(X_test),
    }
