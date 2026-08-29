from datetime import datetime, timedelta
from collections import Counter

import pytz
from flask import Blueprint, render_template
from flask_login import current_user, login_required
from sqlalchemy import func

from misc.extensions import db  # your global SQLAlchemy instance


class ActivityLog(db.Model):
    # this bind key causes troubles in tests, becuase in tests the session is in filesystem
    # alterantivly move ActivityLog to models/activitylog.py and remove binding (entirely ?)
    
    __bind_key__ = "sessions"        # 👈 use the same database as Flask-Session
    __tablename__ = "activity_logs"  # your custom table name

    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(80))
    route = db.Column(db.String(120))
    method = db.Column(db.String(10))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ActivityLog {self.user} {self.route} {self.method}>"
    

def log_activity(path: str, method: str) -> None:
    """Logs user route visits and actions."""
    try:
        user_name = current_user.name if current_user.is_authenticated else "guest"
        new_log = ActivityLog(
            user=user_name, route=path, method=method, timestamp=datetime.utcnow(), # type: ignore
        )
        db.session.add(new_log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[ActivityLog Error] {e}")


def clean_old_logs(days):
    cutoff = datetime.utcnow() - timedelta(days=days)
    deleted = ActivityLog.query.filter(ActivityLog.timestamp < cutoff).delete()
    db.session.commit()
    print(f"🧹 Deleted {deleted} old log entries older than {days} days.")     
    
#show on the bar chart hours activity of the last 30 days
#below in the table most frequently viewed route or next to the chart ?
#or two tables one overall and one for current user

stats_bp = Blueprint("stats", __name__)

def get_hours_map(cutoff):
    # Group by HOUR of the day (0–23)
    hourly_counts = (
        db.session.query(func.extract('hour', ActivityLog.timestamp).label('hour'),
                         func.count(ActivityLog.id).label("count"))
        .filter(ActivityLog.timestamp >= cutoff)
        .group_by('hour')
        .order_by('hour')
        .all()
    )
    # hourly_counts like [('00', 12), ('03', 5), ('13', 42), ...]
    # local offset in hours (example: +1 for Warsaw, +2 for DST)
    local_offset = int((datetime.now() - datetime.utcnow()).total_seconds() // 3600)

    # map {hour_utc: count}
    hour_map = {}
    for row in hourly_counts:
        hour_value = row[0]
        count_value = row[1]
        if hour_value is None:
            continue
        hour_map[(int(hour_value) + local_offset) % 24] = int(count_value)
    return hour_map
    
def get_hours_map_with_dst(cutoff):    
    # get timestamps (as Python datetimes) for last 30 days
    rows = (
        db.session.query(ActivityLog.timestamp)
        .filter(ActivityLog.timestamp >= cutoff)
        .all()
    )
    # rows is list of (timestamp,) tuples

    # choose timezone for display/aggregation (UTC or local)
    local_tz = pytz.timezone("Europe/Warsaw")

    hour_map = Counter()
    for (ts,) in rows:
        # ensure tz-aware and convert to desired zone
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=pytz.UTC)
        local_ts = ts.astimezone(local_tz)
        hour_map[local_ts.hour] += 1
  
    return hour_map

WITH_DST_PRECISE = True

@stats_bp.route('/activity')
@login_required
def activity():
    cutoff = datetime.utcnow() - timedelta(days=30)
    # map {hour_local_time: count}
    hour_map = get_hours_map_with_dst(cutoff) if WITH_DST_PRECISE else get_hours_map(cutoff)

    # convert hours 0–23 with offset wrap-around
    hours = [f"{h:02d}" for h in range(24)]
    counts = [hour_map.get(h, 0) for h in range(24)]

    # Top routes overall
    top_routes_overall = (
        db.session.query(ActivityLog.route, func.count(ActivityLog.id))
        .group_by(ActivityLog.route)
        .order_by(func.count(ActivityLog.id).desc())
        .limit(10)
        .all()
    )

    # Top routes for current user
    top_routes_user = (
        db.session.query(ActivityLog.route, func.count(ActivityLog.id))
        .filter(ActivityLog.user == current_user.name)
        .group_by(ActivityLog.route)
        .order_by(func.count(ActivityLog.id).desc())
        .limit(10)
        .all()
    )

    return render_template(
        "stats.html",
        hours=hours,
        counts=counts,
        top_routes_overall=top_routes_overall,
        top_routes_user=top_routes_user
    )
