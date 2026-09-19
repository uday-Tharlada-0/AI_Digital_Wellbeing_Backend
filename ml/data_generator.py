"""
Synthetic screen-time data generator.

Scolect (like most screen-time apps) has no bundled public dataset - usage
history is personal and generated locally by the tracker. To train and demo
the prediction model out of the box, this module simulates realistic daily
app-usage history with:

  - weekly seasonality (productive apps used more on weekdays, entertainment
    apps more on weekends)
  - a slow trend (productivity drifting up/down over the window)
  - occasional high-leisure "off days"
  - a plausible intraday activity curve for the Time-of-Day chart

Once the app has been running for real, `seed_db.py` should not be re-run;
the trainer (`ml/train_model.py`) will automatically prefer real UsageRecord
history over synthetic data as soon as enough real days exist.
"""

import math
import random
from datetime import date, timedelta

from app_catalog import DEFAULT_APPS

# Typical intraday activity weighting (24 values, hour 0-23), roughly bell
# shaped around the workday with an evening leisure bump.
HOURLY_WEIGHTS = [
    0.2, 0.1, 0.1, 0.1, 0.1, 0.3,   # 0-5   night
    0.8, 1.4, 2.2, 2.6, 2.4, 2.2,   # 6-11  morning ramp-up
    1.8, 2.3, 2.6, 2.4, 2.0, 1.6,   # 12-17 afternoon
    2.0, 2.4, 2.1, 1.6, 1.0, 0.5,   # 18-23 evening leisure
]

FOCUS_PRESETS = {"Deep Work": 60, "Quick Task": 25, "Reading": 45}


def simulate_day(the_date: date, day_index: int, rng: random.Random):
    """Return a dict describing simulated activity for a single day.

    `day_index` counts up from 0 at the start of the generated window and
    drives the slow trend component so later days differ systematically
    from earlier ones (something the model can actually learn).
    """
    is_weekend = the_date.weekday() >= 5

    # Trend: productivity nudges upward ~0.05%/day, entertainment nudges
    # slightly with a slow sine wave (motivation cycles).
    trend_productive = 1 + day_index * 0.0006
    trend_leisure = 1 + 0.08 * math.sin(day_index / 12.0)

    # ~12% chance of a "binge / distracted" day with much higher leisure use
    off_day = rng.random() < 0.12

    app_minutes = {}
    for app in DEFAULT_APPS:
        base = app["base_minutes"]
        boost = app["weekday_boost"]
        weekday_factor = boost if not is_weekend else (2 - boost)

        trend_factor = trend_productive if app["is_productive"] else trend_leisure
        noise = rng.lognormvariate(0, 0.22)  # multiplicative noise, mean ~1

        minutes = base * weekday_factor * trend_factor * noise

        if off_day and not app["is_productive"]:
            minutes *= rng.uniform(1.4, 2.1)
        elif off_day and app["is_productive"]:
            minutes *= rng.uniform(0.5, 0.8)

        app_minutes[app["name"]] = max(0.0, round(minutes, 1))

    total_minutes = sum(app_minutes.values())

    # Distribute total minutes across hours using the weighted curve + noise
    weights = [w * rng.uniform(0.75, 1.25) for w in HOURLY_WEIGHTS]
    weight_sum = sum(weights)
    hourly_minutes = {
        hour: round(total_minutes * (w / weight_sum), 1)
        for hour, w in enumerate(weights)
    }

    # Focus sessions: more likely on weekdays, 0-5 per day
    n_sessions = max(0, round(rng.gauss(2.2 if not is_weekend else 0.8, 1.1)))
    focus_sessions = []
    for _ in range(n_sessions):
        session_type = rng.choice(list(FOCUS_PRESETS.keys()))
        planned = FOCUS_PRESETS[session_type]
        completed = rng.random() < 0.82
        actual = planned if completed else round(planned * rng.uniform(0.3, 0.9))
        focus_sessions.append(
            {
                "session_type": session_type,
                "planned_minutes": planned,
                "actual_minutes": actual,
                "completed": completed,
            }
        )

    return {
        "date": the_date,
        "day_of_week": the_date.weekday(),
        "is_weekend": is_weekend,
        "app_minutes": app_minutes,
        "hourly_minutes": hourly_minutes,
        "focus_sessions": focus_sessions,
        "total_minutes": round(total_minutes, 1),
    }


def generate_history(n_days=180, end_date=None, seed=42):
    """Generate `n_days` of simulated daily activity, oldest first."""
    rng = random.Random(seed)
    end_date = end_date or date.today()
    start_date = end_date - timedelta(days=n_days - 1)

    days = []
    for i in range(n_days):
        d = start_date + timedelta(days=i)
        days.append(simulate_day(d, i, rng))
    return days


if __name__ == "__main__":
    # Quick manual sanity check: `python -m ml.data_generator`
    history = generate_history(n_days=14)
    for day in history:
        print(day["date"], "total:", day["total_minutes"], "sessions:", len(day["focus_sessions"]))
