"""
Trains the next-day usage/productivity predictor.

Run standalone:
    python -m ml.train_model

Or trigger via the API:
    POST /api/predictions/train
"""

import json
import os
from datetime import datetime

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputRegressor

from config import MODEL_DIR
from ml.feature_engineering import (
    FEATURE_COLUMNS,
    TARGET_COLUMNS,
    add_features,
    get_daily_dataset,
)

MODEL_PATH = os.path.join(MODEL_DIR, "usage_predictor.joblib")
METADATA_PATH = os.path.join(MODEL_DIR, "usage_predictor_meta.json")


def train(min_real_days=30, synthetic_days=200, test_size=0.15, random_state=42):
    raw_df, source = get_daily_dataset(min_real_days=min_real_days, synthetic_days=synthetic_days)
    df = add_features(raw_df)

    if len(df) < 20:
        raise RuntimeError(
            f"Not enough data to train ({len(df)} rows after feature engineering). "
            "Run seed_db.py first, or track more days of real usage."
        )

    X = df[FEATURE_COLUMNS].values
    y = df[TARGET_COLUMNS].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, shuffle=True
    )

    model = MultiOutputRegressor(
        RandomForestRegressor(
            n_estimators=300,
            max_depth=8,
            min_samples_leaf=3,
            random_state=random_state,
            n_jobs=-1,
        )
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mae_total_minutes = mean_absolute_error(y_test[:, 0], preds[:, 0])
    mae_score = mean_absolute_error(y_test[:, 1], preds[:, 1])

    # Refit on the full dataset for the deployed model (common practice once
    # a holdout metric has been recorded).
    model.fit(X, y)

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    metadata = {
        "trained_at": datetime.utcnow().isoformat() + "Z",
        "data_source": source,
        "n_samples": len(df),
        "feature_columns": FEATURE_COLUMNS,
        "target_columns": TARGET_COLUMNS,
        "mae_total_minutes": round(float(mae_total_minutes), 2),
        "mae_productivity_score": round(float(mae_score), 2),
    }
    with open(METADATA_PATH, "w") as f:
        json.dump(metadata, f, indent=2)

    return metadata


if __name__ == "__main__":
    result = train()
    print(json.dumps(result, indent=2))
