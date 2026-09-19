from datetime import date, timedelta


def fmt_minutes(mins):
    """Convert float/int minutes -> '5h 42m' style string."""
    mins = int(round(mins or 0))
    h, m = divmod(mins, 60)
    if h and m:
        return f"{h}h {m:02d}m"
    if h:
        return f"{h}h 00m"
    return f"{m}m"


def productivity_score(productive_minutes, total_minutes):
    if not total_minutes:
        return 0
    return round((productive_minutes / total_minutes) * 100)


def date_range(days, end=None):
    """Return list[date] of length `days` ending at `end` (default today), ascending."""
    end = end or date.today()
    return [end - timedelta(days=i) for i in range(days - 1, -1, -1)]


TIME_BUCKETS = {
    "Morning": range(6, 12),
    "Afternoon": range(12, 17),
    "Evening": range(17, 21),
    "Night": list(range(21, 24)) + list(range(0, 6)),
}


def bucket_for_hour(hour):
    for label, hours in TIME_BUCKETS.items():
        if hour in hours:
            return label
    return "Night"
