"""
Turns raw UsageRecord / Application / FocusSession rows into a per-day
feature table suitable for training a next-day usage predictor.

Designed to be usable both from inside the Flask app (via SQLAlchemy) and
as a standalone script (`python -m ml.train_model`), so it talks to the
SQLite file directly through pandas.read_sql rather than importing the
Flask app context.
"""

import pandas as pd
import numpy as np

from models import Application, UsageRecord, FocusSession,UsageSession
from app_catalog import DEFAULT_APPS
from ml.data_generator import generate_history

MIN_REAL_DAYS = 30  # below this, fall back to / top up with synthetic data
CATEGORY_LIST = sorted({a["category"] for a in DEFAULT_APPS})


def _load_from_db():
    """Read daily aggregates from the configured SQLAlchemy database."""
    from flask import has_app_context
    from extensions import db

    if not has_app_context():
        return pd.DataFrame()

    try:
        apps = pd.read_sql(
            db.select(
                Application.id,
                Application.category,
                Application.is_productive
            ).statement,
            db.engine
        )

        usage = pd.read_sql(
            db.select(
                UsageRecord.application_id,
                UsageRecord.date,
                UsageRecord.minutes
            ).statement,
            db.engine
        )

        # Classified mobile sessions are the source of truth for
        # productive minutes.
        sessions = pd.read_sql(
            db.select(
                UsageSession.user_id,
                UsageSession.start_time,
                UsageSession.end_time,
                UsageSession.minutes,
                UsageSession.is_productive,
                UsageSession.classification_status
            ).statement,
            db.engine
        )

        focus = pd.read_sql(
            db.select(
                FocusSession.date,
                FocusSession.actual_minutes,
                FocusSession.completed
            ).statement,
            db.engine
        )

    except Exception:
        return pd.DataFrame()

    if usage.empty:
        return pd.DataFrame()

    # ---------------------------------------------------------
    # TOTAL SCREEN TIME
    # ---------------------------------------------------------
    # UsageRecord remains the source of truth for total usage.
    usage = usage.merge(
        apps,
        left_on="application_id",
        right_on="id",
        how="left"
    )

    usage["date"] = pd.to_datetime(usage["date"])

    daily_total = (
        usage.groupby("date")["minutes"]
        .sum()
        .rename("total_minutes")
    )

    # ---------------------------------------------------------
    # PRODUCTIVE MINUTES
    # ---------------------------------------------------------
    # Use classified UsageSession records instead of
    # Application.is_productive.
    daily_productive = pd.Series(
        dtype="float64",
        name="productive_minutes"
    )

    if not sessions.empty:
        sessions["start_time"] = pd.to_datetime(
            sessions["start_time"]
        )

        classified_sessions = sessions[
            sessions["classification_status"] == "classified"
        ].copy()

        if not classified_sessions.empty:
            classified_sessions["date"] = (
                classified_sessions["start_time"].dt.normalize()
            )

            productive_sessions = classified_sessions[
                classified_sessions["is_productive"] == True
            ]

            if not productive_sessions.empty:
                daily_productive = (
                    productive_sessions
                    .groupby("date")["minutes"]
                    .sum()
                    .rename("productive_minutes")
                )

    # ---------------------------------------------------------
    # CATEGORY DATA
    # ---------------------------------------------------------
    cat_pivot = usage.pivot_table(
        index="date",
        columns="category",
        values="minutes",
        aggfunc="sum",
        fill_value=0
    )

    cat_pivot.columns = [
        f"cat_{str(c).lower()}_minutes"
        for c in cat_pivot.columns
    ]

    df = pd.concat(
        [daily_total, daily_productive],
        axis=1
    ).fillna(0)

    df = df.join(
        cat_pivot,
        how="left"
    ).fillna(0)

    # ---------------------------------------------------------
    # FOCUS DATA
    # ---------------------------------------------------------
    if not focus.empty:
        focus["date"] = pd.to_datetime(focus["date"])

        focus_daily = focus.groupby("date").agg(
            focus_minutes=(
                "actual_minutes",
                lambda s: s.fillna(0).sum()
            ),
            focus_sessions=(
                "completed",
                "count"
            ),
        )

        df = df.join(
            focus_daily,
            how="left"
        )

    df["focus_minutes"] = df.get(
        "focus_minutes",
        0
    )

    df["focus_sessions"] = df.get(
        "focus_sessions",
        0
    )

    df = (
        df.fillna(0)
        .reset_index()
        .rename(columns={"date": "date"})
    )

    return df

def _synthetic_dataframe(n_days=200):
    """Build the same shaped dataframe from the synthetic generator, used
    when there isn't enough real tracked history yet."""
    history = generate_history(n_days=n_days)
    rows = []
    apps_by_name = {a["name"]: a for a in DEFAULT_APPS}

    for day in history:
        row = {"date": pd.Timestamp(day["date"]), "total_minutes": day["total_minutes"]}
        productive = sum(
            m for name, m in day["app_minutes"].items() if apps_by_name[name]["is_productive"]
        )
        row["productive_minutes"] = productive

        cat_sums = {}
        for name, minutes in day["app_minutes"].items():
            cat = apps_by_name[name]["category"].lower()
            cat_sums[f"cat_{cat}_minutes"] = cat_sums.get(f"cat_{cat}_minutes", 0) + minutes
        row.update(cat_sums)

        row["focus_minutes"] = sum(
            s["actual_minutes"] or 0 for s in day["focus_sessions"] if s["completed"]
        )
        row["focus_sessions"] = sum(1 for s in day["focus_sessions"] if s["completed"])
        rows.append(row)

    df = pd.DataFrame(rows).fillna(0)
    return df


def get_daily_dataset(min_real_days=MIN_REAL_DAYS, synthetic_days=200):
    """Return (df, source) where source is 'real' or 'synthetic'.

    If the database has fewer than `min_real_days` days of tracked history,
    synthetic data is used instead so the model can still be trained and
    the /api/predictions endpoints work from day one. Once enough real
    history accumulates, training automatically switches to it.
    """
    real_df = _load_from_db()
    if len(real_df) >= min_real_days:
        return real_df.sort_values("date").reset_index(drop=True), "real"

    synth_df = _synthetic_dataframe(n_days=synthetic_days)
    return synth_df.sort_values("date").reset_index(drop=True), "synthetic"


def add_features(df: pd.DataFrame):
    """Add day-of-week, lag, and rolling-average features + prediction
    targets (next day's total minutes and productivity score)."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    df["productivity_score"] = np.where(
        df["total_minutes"] > 0,
        (df["productive_minutes"] / df["total_minutes"] * 100).round(1),
        0.0,
    )

    df["day_of_week"] = df["date"].dt.dayofweek
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

    for col in ["total_minutes", "productive_minutes", "productivity_score"]:
        df[f"lag1_{col}"] = df[col].shift(1)
        df[f"roll3_{col}"] = df[col].rolling(3, min_periods=1).mean().shift(1)
        df[f"roll7_{col}"] = df[col].rolling(7, min_periods=1).mean().shift(1)

    # Prediction targets: tomorrow's values
    df["target_total_minutes"] = df["total_minutes"].shift(-1)
    df["target_productivity_score"] = df["productivity_score"].shift(-1)

    df = df.dropna().reset_index(drop=True)
    return df


FEATURE_COLUMNS = [
    "day_of_week",
    "is_weekend",
    "lag1_total_minutes",
    "roll3_total_minutes",
    "roll7_total_minutes",
    "lag1_productive_minutes",
    "roll3_productive_minutes",
    "roll7_productive_minutes",
    "lag1_productivity_score",
    "roll3_productivity_score",
    "roll7_productivity_score",
]

TARGET_COLUMNS = ["target_total_minutes", "target_productivity_score"]
