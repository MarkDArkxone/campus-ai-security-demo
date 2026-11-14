from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ApiResponse(BaseModel):
    ok: bool
    message: str
    data: dict[str, Any] | None = None


class AlarmEventOut(BaseModel):
    id: int
    event_type: str
    event_level: str
    message: str
    location: str
    snapshot_path: str | None = None
    person_count: int
    confidence: float | None = None
    created_at: datetime
    status: str

    model_config = {"from_attributes": True}


class ConfigUpdate(BaseModel):
    video_source: int | str | None = None
    conf_threshold: float | None = None
    crowd_threshold: int | None = None
    fall_ratio_threshold: float | None = None
    fall_consecutive_frames: int | None = None
    alarm_cooldown_seconds: int | None = None
    enable_fire_detection: bool | None = None
    fire_conf_threshold: float | None = None
    fire_alarm_cooldown_seconds: int | None = None


class PersonIn(BaseModel):
    name: str
    role: str = "student"
    student_no: str | None = None
    phone: str | None = None
    department: str | None = None
    face_id: str | None = None
    status: str = "normal"


class AccessSimulateIn(BaseModel):
    person_id: int
    device_id: int
    access_type: str = "entry"
    auth_method: str = "manual"


class VisitorIn(BaseModel):
    visitor_name: str
    phone: str | None = None
    reason: str = ""
    host_name: str = ""
    visit_start: datetime | None = None
    visit_end: datetime | None = None


class SensorIn(BaseModel):
    name: str
    sensor_type: str = "smoke"
    location: str = ""
    status: str = "online"
    threshold_value: float = 80.0
    unit: str = ""


class MapPointIn(BaseModel):
    name: str
    point_type: str = "camera"
    related_id: int | None = None
    x: float = 50
    y: float = 50
    location: str = ""
    status: str = "normal"


class UserIn(BaseModel):
    username: str
    password: str
    role: str = "viewer"
    display_name: str = ""
    is_active: bool = True


class UserUpdate(BaseModel):
    password: str | None = None
    role: str | None = None
    display_name: str | None = None
    is_active: bool | None = None
