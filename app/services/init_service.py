from datetime import datetime, timedelta
from os import getenv

from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import AccessDevice, MapPoint, Person, SensorDevice, User


def seed_defaults(db: Session) -> None:
    if not db.query(User).filter(User.username == "admin").first():
        password = getenv("CAMPUS_ADMIN_PASSWORD")
        if not password:
            raise RuntimeError("Set CAMPUS_ADMIN_PASSWORD before the first startup.")
        db.add(
            User(
                username="admin",
                password_hash=hash_password(password),
                role="admin",
                display_name="System Admin",
            )
        )

    if db.query(Person).count() == 0:
        db.add_all(
            [
                Person(name="Zhang San", role="student", student_no="2026001", department="Computer School"),
                Person(name="Li Teacher", role="teacher", department="Computer School"),
                Person(name="Blacklisted Demo", role="blacklist", phone="13800000000", status="blacklist"),
            ]
        )

    if db.query(AccessDevice).count() == 0:
        db.add_all(
            [
                AccessDevice(name="Dormitory Gate A", location="Dormitory Area", device_type="gate", status="online"),
                AccessDevice(name="Main Gate Face Terminal", location="Main Gate", device_type="face_terminal", status="online"),
                AccessDevice(name="Library Card Reader", location="Library", device_type="card_reader", status="offline"),
            ]
        )

    if db.query(SensorDevice).count() == 0:
        db.add_all(
            [
                SensorDevice(name="Canteen Smoke Sensor", sensor_type="smoke", location="Canteen", threshold_value=80, unit="ppm"),
                SensorDevice(name="Lab Temperature Sensor", sensor_type="temperature", location="Lab Building", threshold_value=38, unit="C"),
                SensorDevice(name="Power Room Current Sensor", sensor_type="current", location="Power Room", threshold_value=80, unit="A"),
                SensorDevice(name="Dormitory Humidity Sensor", sensor_type="humidity", location="Dormitory", threshold_value=85, unit="%"),
            ]
        )

    if db.query(MapPoint).count() == 0:
        db.add_all(
            [
                MapPoint(name="Teaching Building Camera", point_type="camera", x=26, y=34, location="Teaching Building", status="normal"),
                MapPoint(name="Dormitory Gate", point_type="access", x=68, y=30, location="Dormitory", status="normal"),
                MapPoint(name="Canteen Smoke Sensor", point_type="sensor", x=42, y=66, location="Canteen", status="normal"),
                MapPoint(name="Playground Camera", point_type="camera", x=74, y=72, location="Playground", status="normal"),
                MapPoint(name="Power Room Current Sensor", point_type="sensor", x=18, y=74, location="Power Room", status="normal"),
            ]
        )

    db.commit()
