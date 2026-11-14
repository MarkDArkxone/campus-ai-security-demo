from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AlarmEvent(Base):
    __tablename__ = "alarm_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    event_level: Mapped[str] = mapped_column(String(32), default="medium")
    message: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String(128), default="Campus Area")
    snapshot_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    person_count: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    status: Mapped[str] = mapped_column(String(32), default="unhandled")


class Person(Base):
    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(32), default="student")
    student_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    department: Mapped[str | None] = mapped_column(String(128), nullable=True)
    face_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="normal")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AccessDevice(Base):
    __tablename__ = "access_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    location: Mapped[str] = mapped_column(String(128), default="Campus Gate")
    device_type: Mapped[str] = mapped_column(String(32), default="gate")
    status: Mapped[str] = mapped_column(String(32), default="online")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AccessRecord(Base):
    __tablename__ = "access_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("persons.id"), nullable=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("access_devices.id"), nullable=True)
    access_type: Mapped[str] = mapped_column(String(32), default="entry")
    auth_method: Mapped[str] = mapped_column(String(32), default="manual")
    result: Mapped[str] = mapped_column(String(32), default="allowed")
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    person: Mapped[Person | None] = relationship()
    device: Mapped[AccessDevice | None] = relationship()


class VisitorRecord(Base):
    __tablename__ = "visitor_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visitor_name: Mapped[str] = mapped_column(String(64), index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    host_name: Mapped[str] = mapped_column(String(64), default="")
    visit_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    visit_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SensorDevice(Base):
    __tablename__ = "sensor_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    sensor_type: Mapped[str] = mapped_column(String(32), default="smoke")
    location: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(32), default="online")
    threshold_value: Mapped[float] = mapped_column(Float, default=80.0)
    unit: Mapped[str] = mapped_column(String(16), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SensorData(Base):
    __tablename__ = "sensor_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sensor_id: Mapped[int] = mapped_column(ForeignKey("sensor_devices.id"), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    sensor: Mapped[SensorDevice] = relationship()


class MapPoint(Base):
    __tablename__ = "map_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    point_type: Mapped[str] = mapped_column(String(32), default="camera")
    related_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    x: Mapped[float] = mapped_column(Float, default=50)
    y: Mapped[float] = mapped_column(Float, default=50)
    location: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(32), default="normal")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="viewer")
    display_name: Mapped[str] = mapped_column(String(64), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
