# Default tracked applications, mirrors the frontend mock data so the seeded
# backend renders identically to the original UI on first run.

DEFAULT_APPS = [
    {"name": "Visual Studio Code", "category": "Development",    "color": "#4a6cf7", "is_productive": True,  "is_visible": True,  "daily_limit_minutes": None, "base_minutes": 80,  "weekday_boost": 1.25},
    {"name": "Google Chrome",      "category": "Browsing",       "color": "#f59e0b", "is_productive": False, "is_visible": True,  "daily_limit_minutes": 180,  "base_minutes": 62,  "weekday_boost": 1.05},
    {"name": "Slack",              "category": "Communication",  "color": "#1fb894", "is_productive": True,  "is_visible": True,  "daily_limit_minutes": None, "base_minutes": 32,  "weekday_boost": 1.4},
    {"name": "Figma",              "category": "Design",         "color": "#f65e4a", "is_productive": True,  "is_visible": True,  "daily_limit_minutes": None, "base_minutes": 24,  "weekday_boost": 1.3},
    {"name": "YouTube",            "category": "Entertainment",  "color": "#ef4444", "is_productive": False, "is_visible": True,  "daily_limit_minutes": 60,   "base_minutes": 28,  "weekday_boost": 0.75},
    {"name": "Spotify",            "category": "Entertainment",  "color": "#22c55e", "is_productive": False, "is_visible": True,  "daily_limit_minutes": None, "base_minutes": 85,  "weekday_boost": 0.9},
    {"name": "Discord",            "category": "Social",         "color": "#818cf8", "is_productive": False, "is_visible": False, "daily_limit_minutes": 45,   "base_minutes": 20,  "weekday_boost": 0.7},
]
