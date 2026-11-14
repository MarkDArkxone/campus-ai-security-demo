from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import AccessDevice, AlarmEvent, SensorDevice
from app.services.video_service import video_service


def dashboard_stats(db: Session) -> dict:
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    alarms_today = db.query(AlarmEvent).filter(AlarmEvent.created_at >= today_start).all()
    high_count = sum(1 for alarm in alarms_today if alarm.event_level == "high")
    latest = db.query(AlarmEvent).order_by(AlarmEvent.created_at.desc()).limit(8).all()

    online_device_names = {d.name for d in db.query(AccessDevice).filter(AccessDevice.status == "online").all()}
    online_device_names |= {d.name for d in db.query(SensorDevice).filter(SensorDevice.status == "online").all()}
    offline_device_names = {d.name for d in db.query(AccessDevice).filter(AccessDevice.status == "offline").all()}
    offline_device_names |= {d.name for d in db.query(SensorDevice).filter(SensorDevice.status == "offline").all()}

    type_stats = Counter(alarm.event_type for alarm in alarms_today)
    trend_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=23)
    trend_alarms = db.query(AlarmEvent.created_at).filter(AlarmEvent.created_at >= trend_start).all()
    trend_counter = Counter(row.created_at.replace(minute=0, second=0, microsecond=0) for row in trend_alarms)
    alarm_trend_24h = [
        {
            "hour": (trend_start + timedelta(hours=offset)).strftime("%H:00"),
            "count": trend_counter.get(trend_start + timedelta(hours=offset), 0),
        }
        for offset in range(24)
    ]
    return {
        "today_alarm_count": len(alarms_today),
        "high_alarm_count": high_count,
        "online_device_count": len(online_device_names),
        "offline_device_count": len(offline_device_names),
        "current_person_count": video_service.current_person_count,
        "alarm_type_stats": dict(type_stats),
        "alarm_trend_24h": alarm_trend_24h,
        "latest_alarms": [
            {
                "id": alarm.id,
                "event_type": alarm.event_type,
                "event_level": alarm.event_level,
                "message": alarm.message,
                "location": alarm.location,
                "created_at": alarm.created_at.isoformat(),
                "status": alarm.status,
            }
            for alarm in latest
        ],
    }
