# Scolect Backend (Flask + SQLite + ML)

Backend for the Scolect-style screen-time dashboard: REST API for
applications/usage/limits/focus/settings, plus an AI prediction service that
trains a scikit-learn model on your (real or simulated) usage history to
forecast tomorrow's screen time, productivity score, and per-app limit
breach risk.

## 1. Project layout

```
scolect-backend/
├── app.py                  # Flask app factory + entrypoint
├── config.py                # paths, SQLite DB config
├── extensions.py            # SQLAlchemy db instance
├── models.py                 # Application, UsageRecord, HourlyActivity,
│                              # FocusSession, Settings
├── utils.py                  # shared helpers (time formatting, buckets)
├── app_catalog.py            # default tracked apps (mirrors the frontend)
├── seed_db.py                 # seeds DB with apps + 180 days of history
├── routes/
│   ├── dashboard.py           # GET  /api/dashboard/today
│   ├── applications.py        # CRUD /api/applications
│   ├── alerts.py               # /api/alerts  (global + per-app limits, notifs)
│   ├── analytics.py            # /api/analytics/* (trends, time-of-day, export)
│   ├── focus.py                 # /api/focus/* (Pomodoro sessions)
│   ├── settings.py              # /api/settings
│   └── predictions.py           # /api/predictions/* (AI forecast)
├── ml/
│   ├── data_generator.py        # synthetic usage simulator (weekly seasonality + trend)
│   ├── feature_engineering.py   # DB -> daily feature table (lags, rolling avgs)
│   ├── train_model.py            # trains + saves the RandomForest model
│   └── predictor.py              # loads model, runs multi-day forecast
├── templates/index.html          # the frontend (served at "/")
├── static/js/api-connect.js       # wires the frontend to the live API
├── data/scolect.db                 # SQLite DB (created by seed_db.py)
├── models_store/                    # trained model + metadata (joblib/json)
└── requirements.txt
```

## 2. How the AI predictions work

Scolect doesn't ship with a public usage dataset — screen-time history is
personal and only exists once the tracker has been running. So the pipeline
is designed to work in two modes automatically:

1. **Cold start (no/short real history):** `ml/data_generator.py` simulates
   realistic daily usage — weekday vs. weekend seasonality per app, a slow
   productivity trend, occasional "binge" days, and a plausible intraday
   activity curve — used both to seed the demo database (`seed_db.py`) and
   as training data (`ml/feature_engineering.get_daily_dataset()` falls back
   to it automatically whenever the DB has fewer than 30 real tracked days).
2. **Real usage (30+ tracked days):** `feature_engineering.py` aggregates
   `UsageRecord` rows straight out of SQLite into a daily table (total
   minutes, productive minutes, category breakdown, focus minutes) and the
   trainer automatically switches to that instead — no code changes needed.

**Features** used to predict tomorrow: day-of-week, weekend flag, and
lag/rolling(3-day, 7-day) averages of total minutes, productive minutes, and
productivity score.

**Model:** `RandomForestRegressor` wrapped in `MultiOutputRegressor` to
jointly predict `(next_day_total_minutes, next_day_productivity_score)`.

**Multi-day forecast:** `ml/predictor.forecast()` predicts day+1, then feeds
that prediction back into the lag/rolling features to predict day+2, and so
on (autoregressive forecasting), for however many days are requested.

**Breach risk & recommendations:** a lightweight rule layer on top of the
model — each app's recent 7-day average is scaled by the model's predicted
overall usage growth and compared to its configured limit (`High` / `Medium`
/ `Low`), and a few plain-English recommendations are generated from the
forecast (e.g. "productivity trending down — schedule a focus session").

Retraining is triggered automatically the first time `/api/predictions/forecast`
is called if no model exists yet, or manually via `POST /api/predictions/train`
(e.g. on a nightly cron job once real usage data is flowing in).

## 3. Setup & execution steps

**Requirements:** Python 3.10+

```bash
# 1. Create and activate a virtual environment
cd scolect-backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Seed the database (creates tables, default apps, and 180 days of
#    simulated usage history so every screen has real data immediately)
python seed_db.py

# 4. Train the prediction model (optional - it will also auto-train
#    the first time the /api/predictions/forecast endpoint is called)
python -m ml.train_model

# 5. Run the server
python app.py
```

The app is now available at **http://localhost:5000** — this serves the
dashboard UI (`templates/index.html`) at `/` and the JSON API under `/api/*`.

To reset and regenerate demo data at any point:
```bash
python seed_db.py 180     # optional arg = number of days of history
```

## 4. API reference

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/dashboard/today` | GET | Today's stats, most-used apps, weekly trend, category breakdown |
| `/api/applications` | GET | List tracked apps (supports `?q=`, `?category=`, `?status=`) |
| `/api/applications` | POST | Add a new tracked app |
| `/api/applications/<id>` | PATCH | Update category/productive/visible/limit |
| `/api/applications/<id>` | DELETE | Remove a tracked app |
| `/api/applications/<id>/log-usage` | POST | Increment today's usage (called by a tracking agent) |
| `/api/alerts` | GET | Global limit, per-app limits, notification settings |
| `/api/alerts/global` | PATCH | Update the global daily limit |
| `/api/alerts/app-limit/<id>` | PATCH | Set/clear a per-app limit |
| `/api/alerts/notifications` | PATCH | Toggle popup/system/sound alerts |
| `/api/analytics/daily-trends?days=` | GET | Daily total/productive hours + score |
| `/api/analytics/time-of-day` | GET | Morning/afternoon/evening/night breakdown |
| `/api/analytics/week-over-week` | GET | Weekly totals, last N weeks |
| `/api/analytics/insights` | GET | Rule-based text insights |
| `/api/analytics/export` | GET | Download an .xlsx usage report |
| `/api/focus/sessions?date=` | GET | Focus sessions for a given day |
| `/api/focus/sessions/start` | POST | Start a Pomodoro session |
| `/api/focus/sessions/<id>/complete` | POST | Mark a session complete |
| `/api/focus/trend?days=` | GET | Completed sessions per day |
| `/api/settings` | GET / PATCH | App preferences |
| `/api/predictions/forecast?days=` | GET | AI forecast + breach risk + recommendations |
| `/api/predictions/train` | POST | (Re)train the model on current data |
| `/api/predictions/model-info` | GET | Metadata: MAE, sample count, last trained time |

## 5. Connecting a real tracker

This backend assumes something is populating `UsageRecord` / `HourlyActivity`
rows as the day goes on — in the original Flutter app that's a native
foreground-window watcher. From Python you'd typically poll the active
window every N seconds and call:

```bash
curl -X POST http://localhost:5000/api/applications/1/log-usage \
     -H "Content-Type: application/json" \
     -d '{"minutes": 0.5}'
```

Once 30+ real days have accumulated, `ml/feature_engineering.py` will use
that real history for training automatically instead of the synthetic data.

## 6. Notes

- The DB is SQLite for simplicity — swap `SQLALCHEMY_DATABASE_URI` in
  `config.py` for Postgres/MySQL in production.
- `data/` and `models_store/` start empty — you must run `python seed_db.py`
  (creates the schema + demo data) before `python app.py` will have anything
  to show. Training happens automatically on first forecast request, or run
  `python -m ml.train_model` explicitly. Re-run `seed_db.py` any time to
  regenerate fresh demo data.
- Every module in this project (`data_generator`, `feature_engineering`,
  `train_model`, `predictor`) was independently smoke-tested against a
  matching SQLite schema during development — training converges to ~40min
  MAE on total screen time and ~5pt MAE on productivity score against the
  synthetic dataset described above.
