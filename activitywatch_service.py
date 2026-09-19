import json
import re
from datetime import date, datetime, timedelta, timezone
from urllib.request import Request, urlopen
from urllib.parse import quote, urlparse

from extensions import db
from app_catalog import DEFAULT_APPS
from models import ActivityEvent, Application, HourlyActivity, UsageRecord


CATEGORY_RULES = {
    "Development": ("code", "visual studio", "pycharm", "terminal", "github", "gitlab", "stackoverflow"),
    "Communication": ("slack", "discord", "teams", "zoom", "meet", "messenger", "whatsapp"),
    "Entertainment": ("youtube", "netflix", "spotify", "twitch", "reddit", "game"),
    "Design": ("figma", "photoshop", "illustrator", "canva"),
    "Study": ("coursera", "udemy", "khan", "wikipedia", "docs.google", "notion", "chatgpt"),
    "System": ("searchhost", "shellhost", "explorer", "dwm", "runtimebroker", "applicationframehost"),
}
PRODUCTIVE_CATEGORIES = {"Development", "Communication", "Design", "Study"}
IGNORED_BUCKET_WORDS = ("afk", "heartbeat", "walkaway")
APPLICATION_ALIASES = {
    "code.exe": "Visual Studio Code",
    "visual studio code": "Visual Studio Code",
    "chrome.exe": "Google Chrome",
    "google chrome": "Google Chrome",
    "msedge.exe": "Microsoft Edge",
    "microsoft edge": "Microsoft Edge",
    "windowsterminal.exe": "Windows Terminal",
    "windows terminal": "Windows Terminal",
    "chatgpt classic.exe": "ChatGPT",
}


def _request_json(base_url, path):
    normalized_path = path.strip("/")
    suffix = "/" if path.endswith("/") else ""
    url = f"{base_url.rstrip('/')}/{normalized_path}{suffix}"
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse_time(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def classify(application_name, website="", title=""):
    normalized = normalize_application(application_name)
    if normalized in {"Google Chrome", "Microsoft Edge"}:
        return "Browsing", False
    if normalized.lower().endswith(("searchhost.exe", "shellhost.exe", "explorer.exe")):
        return "System", False
    text = f"{application_name} {website} {title}".lower()
    for category, terms in CATEGORY_RULES.items():
        if any(term in text for term in terms):
            return category, category in PRODUCTIVE_CATEGORIES
    if website:
        return "Browsing", False
    return "Uncategorized", False


def normalize_application(application_name):
    key = re.sub(r"\s+", " ", str(application_name).strip().lower())
    return APPLICATION_ALIASES.get(key, str(application_name).strip())


def _event_values(bucket_id, index, event):
    data = event.get("data") or {}
    website = data.get("url") or data.get("domain") or ""
    title = data.get("title") or data.get("window_title") or ""
    application = data.get("app") or data.get("application") or data.get("name")
    if (not application or str(application).lower() in {"browser", "web"}) and website:
        application = urlparse(website if "://" in website else f"https://{website}").netloc or website
    application = normalize_application(application or bucket_id)
    start = _parse_time(event.get("timestamp"))
    duration = max(0.0, float(event.get("duration") or 0))
    category, productive = classify(application, website, title)
    return {
        "source_event_id": f"{bucket_id}:{index}:{event.get('timestamp')}:{duration}",
        "application_name": str(application)[:120],
        "website": str(website)[:500] or None,
        "category": category,
        "is_productive": productive,
        "start_time": start,
        "end_time": start + timedelta(seconds=duration),
        "duration_seconds": duration,
    }


def _events_from_buckets(base_url):
    buckets = _request_json(base_url, "/api/0/buckets/")
    has_browser_bucket = any(
        str(bucket.get("type", "")).lower() in {"web", "browser"}
        for bucket in buckets.values()
    )
    imported = []
    for bucket_id, bucket in buckets.items():
        if any(word in bucket_id.lower() for word in IGNORED_BUCKET_WORDS):
            continue
        bucket_type = str(bucket.get("type", "")).lower()
        if bucket_type and bucket_type not in {"app", "web", "window", "currentwindow", "browser"}:
            continue
        events = _request_json(base_url, f"/api/0/buckets/{quote(bucket_id, safe='')}/events")
        for index, event in enumerate(events):
            if event.get("data", {}).get("url") or event.get("data", {}).get("domain"):
                has_browser_bucket = True
            if event.get("duration", 0) and event.get("timestamp"):
                imported.append(_event_values(bucket_id, index, event))
    return imported, has_browser_bucket


def _ensure_application(name, category, productive):
    application = Application.query.filter_by(name=name).first()
    if application:
        if application.category in {"Uncategorized", "System"}:
            application.category = category
        if productive:
            application.is_productive = True
        return application
    application = Application(name=name, category=category, is_productive=productive, is_visible=True)
    db.session.add(application)
    db.session.flush()
    return application


def aggregate_events(user_id):
    events = ActivityEvent.query.filter_by(user_id=user_id).all()
    daily = {}
    hourly = {}
    app_metadata = {}
    for event in events:
        minutes = event.duration_seconds / 60
        day = event.start_time.date()
        daily[(event.application_name, day)] = daily.get((event.application_name, day), 0) + minutes
        hourly[(day, event.start_time.hour)] = hourly.get((day, event.start_time.hour), 0) + minutes
        category = event.user_category or event.category
        productive = category in PRODUCTIVE_CATEGORIES or category in {"Work", "Study"}
        app_metadata[event.application_name] = (category, productive)

    for (name, day), minutes in daily.items():
        category, productive = app_metadata[name]
        application = _ensure_application(name, category, productive)
        record = UsageRecord.query.filter_by(application_id=application.id, date=day).first()
        if record:
            record.minutes = round(minutes, 1)
        else:
            db.session.add(UsageRecord(application_id=application.id, date=day, minutes=round(minutes, 1)))
    for (day, hour), minutes in hourly.items():
        record = HourlyActivity.query.filter_by(date=day, hour=hour).first()
        if record:
            record.minutes = round(minutes, 1)
        else:
            db.session.add(HourlyActivity(date=day, hour=hour, minutes=round(minutes, 1)))


def repair_application_categories():
    for application in Application.query.all():
        category, productive = classify(application.name)
        if application.category == "Uncategorized" and category != "Uncategorized":
            application.category = category
        if productive and category == application.category:
            application.is_productive = True


def sync_activitywatch(user_id, base_url="http://localhost:5600"):
    values, has_browser_bucket = _events_from_buckets(base_url)
    added = 0
    for value in values:
        exists = ActivityEvent.query.filter_by(user_id=user_id, source="activitywatch", source_event_id=value["source_event_id"]).first()
        if exists:
            if exists.classification_source != "user":
                exists.application_name = value["application_name"]
                exists.website = value["website"]
                exists.category = value["category"]
                exists.is_productive = value["is_productive"]
            continue
        db.session.add(ActivityEvent(user_id=user_id, source="activitywatch", **value))
        added += 1
    # ActivityWatch is the source of truth for the current day. Remove demo
    # and legacy executable totals before rebuilding today's real totals.
    today = date.today()
    known_names = {item["name"] for item in DEFAULT_APPS}
    known_names.update(APPLICATION_ALIASES)
    known_names.update({"SearchHost.exe", "ShellHost.exe", "explorer.exe"})
    app_ids = [row.id for row in Application.query.filter(Application.name.in_(known_names)).all()]
    if app_ids:
        UsageRecord.query.filter(UsageRecord.application_id.in_(app_ids), UsageRecord.date == today).delete(synchronize_session=False)
    repair_application_categories()
    aggregate_events(user_id)
    db.session.commit()
    model_retrained = False
    try:
        from ml.train_model import train

        train()
        model_retrained = True
    except Exception:
        pass
    return {
        "received": len(values),
        "added": added,
        "source": base_url,
        "model_retrained": model_retrained,
        "browser_watcher": has_browser_bucket,
    }


def ingest_events(user_id, payload):
    events = payload if isinstance(payload, list) else payload.get("events", [])
    added = 0
    for index, value in enumerate(events):
        application = normalize_application(value.get("application_name") or value.get("app") or "Unknown")
        start = _parse_time(value["start_time"])
        duration = float(value.get("duration_seconds", value.get("duration", 0)))
        category, productive = classify(application, value.get("website", ""), value.get("title", ""))
        source_id = str(value.get("source_event_id") or f"manual:{start.isoformat()}:{index}")
        if ActivityEvent.query.filter_by(user_id=user_id, source="manual", source_event_id=source_id).first():
            continue
        db.session.add(ActivityEvent(
            user_id=user_id,
            source="manual",
            source_event_id=source_id,
            application_name=application[:120],
            website=(value.get("website") or "")[:500] or None,
            category=category,
            is_productive=productive,
            start_time=start,
            end_time=start + timedelta(seconds=max(0, duration)),
            duration_seconds=max(0, duration),
        ))
        added += 1
    aggregate_events(user_id)
    db.session.commit()
    return {"received": len(events), "added": added, "source": "manual"}
