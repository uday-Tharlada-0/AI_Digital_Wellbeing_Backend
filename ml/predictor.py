import json
import os
from datetime import date, timedelta

import joblib
import numpy as np
import pandas as pd

from config import MODEL_DIR
from ml.feature_engineering import FEATURE_COLUMNS, get_daily_dataset
from ml.train_model import MODEL_PATH, METADATA_PATH, train as train_model


class ModelNotTrainedError(Exception):
    pass


def _load_model():
    if not os.path.exists(MODEL_PATH):
        raise ModelNotTrainedError(
            "No trained model found. Call POST /api/predictions/train first."
        )
    return joblib.load(MODEL_PATH)


def get_metadata():
    if not os.path.exists(METADATA_PATH):
        return None
    with open(METADATA_PATH) as f:
        return json.load(f)


def ensure_model(auto_train=True):
    """Load the model, training it on the fly the first time if missing."""
    if not os.path.exists(MODEL_PATH):
        if not auto_train:
            raise ModelNotTrainedError("Model not trained yet.")
        train_model()
    return _load_model()


def _validate_history(df: pd.DataFrame, min_rows=8):
    if len(df) < min_rows:
        raise RuntimeError(
            f"Not enough historical days to seed a forecast ({len(df)} available, "
            f"need at least {min_rows}). Run seed_db.py or track more days."
        )


def forecast(days=7, auto_train=True):
    model = ensure_model(auto_train=auto_train)
    raw_df, source = get_daily_dataset()
    _validate_history(raw_df)

    # "Today" is simply the most recent tracked day - read directly off the
    # raw data rather than the shifted/feature-engineered frame (whose last
    # row is dropped because it has no next-day target yet).
    today_total = float(raw_df["total_minutes"].iloc[-1])
    today_productive = float(raw_df["productive_minutes"].iloc[-1])
    today_score = round((today_productive / today_total * 100)) if today_total else 0

    # Running state used to recompute lag/rolling features as we predict
    # further into the future (autoregressive multi-step forecast).
    history_totals = list(raw_df["total_minutes"].tail(7))
    history_scores = list(
        (raw_df["productive_minutes"] / raw_df["total_minutes"].replace(0, np.nan) * 100)
        .fillna(0)
        .tail(7)
    )
    history_productive = list(raw_df["productive_minutes"].tail(7))

    last_total = history_totals[-1]
    last_productive = history_productive[-1]
    last_score = history_scores[-1]

    results = []
    current_date = date.today()

    for step in range(days):
        target_date = current_date + timedelta(days=step + 1)
        dow = target_date.weekday()

        feature_row = {
            "day_of_week": dow,
            "is_weekend": int(dow >= 5),
            "lag1_total_minutes": last_total,
            "roll3_total_minutes": float(np.mean(history_totals[-3:])),
            "roll7_total_minutes": float(np.mean(history_totals[-7:])),
            "lag1_productive_minutes": last_productive,
            "roll3_productive_minutes": float(np.mean(history_productive[-3:])),
            "roll7_productive_minutes": float(np.mean(history_productive[-7:])),
            "lag1_productivity_score": last_score,
            "roll3_productivity_score": float(np.mean(history_scores[-3:])),
            "roll7_productivity_score": float(np.mean(history_scores[-7:])),
        }
        X = np.array([[feature_row[c] for c in FEATURE_COLUMNS]])
        pred_total, pred_score = model.predict(X)[0]
        pred_total = max(0.0, float(pred_total))
        pred_score = float(np.clip(pred_score, 0, 100))
        pred_productive = pred_total * pred_score / 100

        results.append(
            {
                "date": target_date.isoformat(),
                "label": target_date.strftime("%a %b %d"),
                "predicted_total_minutes": round(pred_total, 1),
                "predicted_total_hours": round(pred_total / 60, 2),
                "predicted_productive_minutes": round(pred_productive, 1),
                "predicted_productivity_score": round(pred_score),
            }
        )

        # roll the autoregressive window forward
        history_totals.append(pred_total)
        history_productive.append(pred_productive)
        history_scores.append(pred_score)
        last_total, last_productive, last_score = pred_total, pred_productive, pred_score

    return {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "data_source": source,
        "today_total_minutes": round(today_total, 1),
        "today_productivity_score": today_score,
        "forecast": results,
    }


def breach_risk(applications, forecast_result):
    """Heuristic (not ML) risk estimate per app-limit, combining each app's
    recent trend with the model's predicted overall-usage change."""
    if not forecast_result["forecast"]:
        return []

    tomorrow_growth = (
        forecast_result["forecast"][0]["predicted_total_minutes"]
        / forecast_result["today_total_minutes"]
        if forecast_result["today_total_minutes"]
        else 1.0
    )

    risks = []
    for app in applications:
        if not app.get("daily_limit_minutes"):
            continue
        recent_avg = app.get("weekly_avg_minutes", 0)
        projected = recent_avg * tomorrow_growth
        ratio = projected / app["daily_limit_minutes"] if app["daily_limit_minutes"] else 0

        if ratio >= 1:
            level = "High"
        elif ratio >= 0.75:
            level = "Medium"
        else:
            level = "Low"

        risks.append(
            {
                "application": app["name"],
                "projected_minutes": round(projected, 1),
                "limit_minutes": app["daily_limit_minutes"],
                "risk": level,
            }
        )

    return sorted(risks, key=lambda r: {"High": 0, "Medium": 1, "Low": 2}[r["risk"]])


def recommendations(forecast_result, risks, today_score):
    out = []
    tomorrow = forecast_result["forecast"][0] if forecast_result["forecast"] else None

    high_risk = [r for r in risks if r["risk"] == "High"]
    for r in high_risk[:2]:
        out.append(
            {
                "icon": "⚠️",
                "text": f"{r['application']} is projected to exceed its limit tomorrow — consider enabling a hard block.",
            }
        )

    if tomorrow and tomorrow["predicted_productivity_score"] < today_score:
        out.append(
            {
                "icon": "🕐",
                "text": "Predicted productivity is trending down — schedule a Deep Work focus session early tomorrow.",
            }
        )
    elif tomorrow and tomorrow["predicted_productivity_score"] >= today_score:
        out.append(
            {
                "icon": "✅",
                "text": "Predicted productivity is trending up — keep tomorrow's routine similar to today's.",
            }
        )

    if tomorrow and tomorrow["predicted_total_hours"] > 7:
        out.append(
            {
                "icon": "🌙",
                "text": f"Total screen time is forecast at {tomorrow['predicted_total_hours']}h — plan a screen-free break in the evening.",
            }
        )

    if not out:
        out.append({"icon": "👍", "text": "No red flags predicted for tomorrow. Keep up the current pace."})

    return out
