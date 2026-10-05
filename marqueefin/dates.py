"""Dates: local days from Jellyfin's and Seerr's timestamps."""

from datetime import datetime, timedelta


def local_today():
    """Today in the local time zone, as 'YYYY-MM-DD'."""
    return datetime.now().astimezone().date().isoformat()


def utc_stamp(value):
    """'2026-01-17T17:26:41.8020000Z' -> '2026-01-17T17:26:41Z' (sortable as text)."""
    return value[:19] + "Z" if value and len(value) >= 19 else None


def year_of(date_str):
    try:
        return int(date_str[:4])
    except (TypeError, ValueError):
        return None


def local_date(stamp):
    """'2018-07-03T22:00:00Z' -> '2018-07-04'. Jellyfin stores local midnight as UTC, so
    east of UTC the date part is a day early: noon or later is the next day."""
    if not stamp:
        return None
    try:
        dt = datetime.fromisoformat(stamp[:19])
    except ValueError:
        return stamp[:10]
    return (dt + timedelta(days=1) if dt.hour >= 12 else dt).date().isoformat()


def utc_to_local_date(stamp):
    """'2026-09-12T22:30:00.000Z' -> local date '2026-09-13'."""
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone().date().isoformat()
    except (AttributeError, ValueError):
        return None
