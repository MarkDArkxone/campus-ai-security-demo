from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.alarm_manager import alarm_manager
from app.models import AccessDevice, AccessRecord, AlarmEvent, MapPoint, Person, SensorDevice, VisitorRecord


def initialize_demo_data(db: Session) -> dict:
    """Create classroom-demo data without deleting the user's existing records."""
    persons = [
        Person(name="张三", role="student", student_no="2026001", phone="13800000001", department="计算机学院", status="normal"),
        Person(name="李老师", role="teacher", phone="13800000002", department="信息工程学院", status="normal"),
        Person(name="王保卫", role="staff", phone="13800000003", department="保卫处", status="normal"),
        Person(name="黑名单演示人员", role="blacklist", phone="13900000000", department="校外人员", status="blacklist"),
    ]
    devices = [
        AccessDevice(name="学校正门闸机", location="学校正门", device_type="gate", status="online"),
        AccessDevice(name="宿舍区人脸终端", location="宿舍区", device_type="face_terminal", status="online"),
        AccessDevice(name="图书馆刷卡器", location="图书馆", device_type="card_reader", status="online"),
    ]
    sensors = [
        SensorDevice(name="食堂烟雾传感器", sensor_type="smoke", location="食堂", status="online", threshold_value=80, unit="ppm"),
        SensorDevice(name="实验楼温度传感器", sensor_type="temperature", location="实验楼", status="online", threshold_value=38, unit="C"),
        SensorDevice(name="配电房电流传感器", sensor_type="current", location="配电房", status="online", threshold_value=80, unit="A"),
        SensorDevice(name="宿舍湿度传感器", sensor_type="humidity", location="宿舍区", status="online", threshold_value=85, unit="%"),
    ]
    points = [
        MapPoint(name="教学楼摄像头", point_type="camera", x=24, y=34, location="教学楼", status="normal"),
        MapPoint(name="宿舍门禁", point_type="access", x=68, y=29, location="宿舍区", status="normal"),
        MapPoint(name="食堂烟雾传感器", point_type="sensor", x=43, y=66, location="食堂", status="normal"),
        MapPoint(name="操场摄像头", point_type="camera", x=74, y=72, location="操场", status="normal"),
        MapPoint(name="配电房电流传感器", point_type="sensor", x=18, y=74, location="配电房", status="normal"),
    ]
    visitors = [
        VisitorRecord(visitor_name="赵访客", phone="13700000001", reason="项目交流", host_name="李老师", status="approved"),
        VisitorRecord(visitor_name="钱访客", phone="13700000002", reason="设备维护", host_name="王保卫", status="pending"),
        VisitorRecord(visitor_name="孙访客", phone="13700000003", reason="临时拜访", host_name="张三", status="rejected"),
    ]

    created = {
        "persons": add_missing(db, Person, Person.name, persons),
        "access_devices": add_missing(db, AccessDevice, AccessDevice.name, devices),
        "sensor_devices": add_missing(db, SensorDevice, SensorDevice.name, sensors),
        "map_points": add_missing(db, MapPoint, MapPoint.name, points),
        "visitors": add_missing(db, VisitorRecord, VisitorRecord.visitor_name, visitors),
    }

    now = datetime.utcnow()
    history = [
        AlarmEvent(event_type="fence_intrusion", event_level="high", message="演示历史告警：人员进入教学楼电子围栏", location="教学楼", created_at=now - timedelta(minutes=45)),
        AlarmEvent(event_type="crowd_gathering", event_level="medium", message="演示历史告警：操场人员聚集", location="操场", person_count=8, created_at=now - timedelta(minutes=30)),
        AlarmEvent(event_type="smoke_warning", event_level="medium", message="演示历史告警：食堂烟雾传感器超过阈值", location="食堂", created_at=now - timedelta(minutes=18)),
        AlarmEvent(event_type="access_denied", event_level="high", message="演示历史告警：黑名单人员尝试通行", location="宿舍区", person_count=1, created_at=now - timedelta(minutes=8)),
    ]
    added_alarms = 0
    for alarm in history:
        exists = db.query(AlarmEvent).filter(AlarmEvent.event_type == alarm.event_type, AlarmEvent.message == alarm.message).first()
        if not exists:
            db.add(alarm)
            added_alarms += 1
    created["history_alarms"] = added_alarms
    db.commit()
    return created


def add_missing(db: Session, model, unique_column, rows: list) -> int:
    count = 0
    for row in rows:
        value = getattr(row, unique_column.key)
        if not db.query(model).filter(unique_column == value).first():
            db.add(row)
            count += 1
    return count


async def trigger_demo_alarm(db: Session, alarm_type: str) -> dict:
    messages = {
        "fence": ("fence_intrusion", "high", "演示触发：人员进入电子围栏危险区域", "教学楼", 1),
        "crowd": ("crowd_gathering", "medium", "演示触发：同一画面人员数量超过阈值", "操场", 8),
        "fall": ("fall_suspected", "high", "演示触发：检测到疑似跌倒姿态", "校园主干道", 1),
        "smoke": ("smoke_warning", "medium", "演示触发：烟雾传感器超过安全阈值", "食堂", 0),
        "temperature": ("temperature_warning", "medium", "演示触发：实验楼温度超过安全阈值", "实验楼", 0),
        "current": ("electricity_warning", "high", "演示触发：配电房电流超过安全阈值", "配电房", 0),
    }
    if alarm_type == "blacklist":
        return await trigger_blacklist_access(db)
    if alarm_type not in messages:
        raise ValueError("Unknown demo alarm type")
    event_type, level, message, location, person_count = messages[alarm_type]
    alarm = await alarm_manager.create_alarm(
        event_type,
        level,
        message,
        frame=None,
        person_count=person_count,
        location=location,
        cooldown=0,
    )
    return {"event_type": alarm.event_type if alarm else event_type, "message": message}


async def run_demo_sequence(db: Session) -> dict:
    """Prepare data and fire a compact set of demo alarms for presentations."""
    init_result = initialize_demo_data(db)
    triggered = []
    for alarm_type in ["fence", "crowd", "fall", "smoke", "temperature", "current", "blacklist"]:
        result = await trigger_demo_alarm(db, alarm_type)
        triggered.append(result["event_type"])
    return {"initialized": init_result, "triggered": triggered}


async def trigger_blacklist_access(db: Session) -> dict:
    person = db.query(Person).filter(Person.status == "blacklist").first()
    device = db.query(AccessDevice).filter(AccessDevice.status == "online").first()
    if not person:
        person = Person(name="黑名单演示人员", role="blacklist", phone="13900000000", status="blacklist")
        db.add(person)
        db.commit()
        db.refresh(person)
    if not device:
        device = AccessDevice(name="学校正门闸机", location="学校正门", device_type="gate", status="online")
        db.add(device)
        db.commit()
        db.refresh(device)
    record = AccessRecord(
        person_id=person.id,
        device_id=device.id,
        access_type="entry",
        auth_method="manual",
        result="denied",
        message="Demo blacklist access denied",
    )
    db.add(record)
    db.commit()
    await alarm_manager.create_alarm(
        "access_denied",
        "high",
        f"演示触发：黑名单人员 {person.name} 尝试通过 {device.name}",
        person_count=1,
        location=device.location,
        cooldown=0,
    )
    return {"event_type": "access_denied", "message": record.message}
