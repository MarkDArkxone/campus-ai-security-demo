import asyncio
import time
from datetime import datetime
from pathlib import Path

import cv2

from app.config import SNAPSHOT_DIR, runtime_config
from app.database import SessionLocal
from app.models import AlarmEvent, MapPoint
from app.services.websocket_manager import websocket_manager


class AlarmManager:
    def __init__(self) -> None:
        self.last_alarm_at: dict[str, float] = {}
        self.loop: asyncio.AbstractEventLoop | None = None
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    def should_create(self, event_type: str, cooldown: int | None = None) -> bool:
        now = time.time()
        seconds = cooldown if cooldown is not None else runtime_config.alarm_cooldown_seconds
        return now - self.last_alarm_at.get(event_type, 0) >= seconds

    def save_snapshot(self, frame, event_type: str) -> str | None:
        if frame is None:
            return None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{event_type}_{timestamp}.jpg"
        file_path = Path(SNAPSHOT_DIR) / filename
        try:
            SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
            ok = cv2.imwrite(str(file_path), frame)
        except Exception:
            return None
        if not ok:
            return None
        return f"/static/snapshots/{filename}"

    async def create_alarm(
        self,
        event_type: str,
        event_level: str,
        message: str,
        frame=None,
        person_count: int = 0,
        confidence: float | None = None,
        location: str = "Campus Area",
        cooldown: int | None = None,
    ) -> AlarmEvent | None:
        if not self.should_create(event_type, cooldown):
            return None

        self.last_alarm_at[event_type] = time.time()
        snapshot_path = self.save_snapshot(frame, event_type)

        try:
            with SessionLocal() as db:
                alarm = AlarmEvent(
                    event_type=event_type,
                    event_level=event_level,
                    message=message,
                    location=location,
                    snapshot_path=snapshot_path,
                    person_count=person_count,
                    confidence=confidence,
                )
                db.add(alarm)

                point = self._find_related_map_point(db, event_type, location)
                if point:
                    point.status = "alarm" if event_level == "high" else "warning"

                db.commit()
                db.refresh(alarm)
                payload = {
                    "id": alarm.id,
                    "event_type": alarm.event_type,
                    "event_level": alarm.event_level,
                    "message": alarm.message,
                    "location": alarm.location,
                    "snapshot_path": alarm.snapshot_path,
                    "person_count": alarm.person_count,
                    "confidence": alarm.confidence,
                    "created_at": alarm.created_at.isoformat(),
                    "status": alarm.status,
                    "map_point_id": point.id if point else None,
                }
        except Exception:
            self.last_alarm_at.pop(event_type, None)
            return None

        await websocket_manager.broadcast(payload)
        return alarm

    def _find_related_map_point(self, db, event_type: str, location: str) -> MapPoint | None:
        if event_type in {"access_denied"}:
            point_type = "access"
        elif event_type in {"smoke_warning", "temperature_warning", "electricity_warning", "smoke_detected", "fire_detected", "fire_risk_high"}:
            point_type = "sensor"
        else:
            point_type = "camera"

        query = db.query(MapPoint).filter(MapPoint.point_type == point_type)
        if location:
            matched = query.filter(MapPoint.location.contains(location)).first()
            if matched:
                return matched
        return query.first()

    def create_alarm_from_thread(self, *args, **kwargs) -> None:
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.create_alarm(*args, **kwargs), self.loop)
            return
        try:
            asyncio.run(self.create_alarm(*args, **kwargs))
        except RuntimeError:
            pass


alarm_manager = AlarmManager()
