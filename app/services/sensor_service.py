import asyncio
import random
from datetime import datetime

from app.alarm_manager import alarm_manager
from app.database import SessionLocal
from app.models import SensorData, SensorDevice


class SensorSimulator:
    def __init__(self) -> None:
        self.running = False
        self.task: asyncio.Task | None = None
        self.last_values: dict[int, float] = {}
        self.abnormal_smoke_until: float = 0
        self.last_error: str | None = None

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        try:
            self.task = asyncio.create_task(self._loop())
        except RuntimeError as exc:
            self.running = False
            self.last_error = str(exc)

    def stop(self) -> None:
        self.running = False
        if self.task:
            self.task.cancel()
            self.task = None

    async def _loop(self) -> None:
        while self.running:
            try:
                await self.generate_once()
                self.last_error = None
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.last_error = str(exc)
            await asyncio.sleep(3)

    async def generate_once(self, abnormal_type: str | None = None) -> None:
        with SessionLocal() as db:
            sensors = db.query(SensorDevice).filter(SensorDevice.status == "online").all()
            for sensor in sensors:
                value = self._value_for(sensor, abnormal_type)
                data = SensorData(sensor_id=sensor.id, value=value, unit=sensor.unit)
                db.add(data)
                self.last_values[sensor.id] = value
                if value > sensor.threshold_value:
                    try:
                        await self._create_warning(sensor, value)
                    except Exception as exc:
                        self.last_error = str(exc)
            db.commit()

    def _value_for(self, sensor: SensorDevice, abnormal_type: str | None = None) -> float:
        if abnormal_type == sensor.sensor_type:
            return round(sensor.threshold_value + random.uniform(10, 35), 2)
        if sensor.sensor_type == "smoke":
            return round(random.uniform(8, 35), 2)
        if sensor.sensor_type == "temperature":
            return round(random.uniform(22, 32), 2)
        if sensor.sensor_type == "current":
            return round(random.uniform(15, 55), 2)
        if sensor.sensor_type == "voltage":
            return round(random.uniform(210, 230), 2)
        return round(random.uniform(35, 75), 2)

    async def _create_warning(self, sensor: SensorDevice, value: float) -> None:
        event_type = "sensor_warning"
        level = "medium"
        if sensor.sensor_type == "smoke":
            event_type = "smoke_warning"
            self.abnormal_smoke_until = datetime.utcnow().timestamp() + 20
        elif sensor.sensor_type == "temperature":
            event_type = "temperature_warning"
        elif sensor.sensor_type == "current":
            event_type = "electricity_warning"
            level = "high"
        await alarm_manager.create_alarm(
            event_type,
            level,
            f"{sensor.name} value {value}{sensor.unit} exceeds threshold {sensor.threshold_value}{sensor.unit}",
            location=sensor.location,
        )

    def has_recent_smoke_abnormal(self) -> bool:
        return datetime.utcnow().timestamp() < self.abnormal_smoke_until


sensor_simulator = SensorSimulator()
