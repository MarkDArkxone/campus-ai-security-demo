import os
from secrets import token_urlsafe
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

VIDEO_SOURCE = 0
MODEL_NAME = "yolov8n.pt"
CONF_THRESHOLD = 0.4
CROWD_THRESHOLD = 5
FALL_RATIO_THRESHOLD = 1.35
FALL_CONSECUTIVE_FRAMES = 5
ALARM_COOLDOWN_SECONDS = 10

FIRE_MODEL_PATH = ""
ENABLE_FIRE_DETECTION = True
FIRE_CONF_THRESHOLD = 0.4
FIRE_ALARM_COOLDOWN_SECONDS = 15

SNAPSHOT_DIR = BASE_DIR / "app" / "static" / "snapshots"
DATABASE_URL = f"sqlite:///{BASE_DIR / 'data' / 'campus_security.db'}"
DEFAULT_FENCE_POINTS = [(100, 100), (500, 100), (500, 350), (100, 350)]
SECRET_KEY = os.getenv("CAMPUS_SESSION_SECRET") or token_urlsafe(48)

# Frontend/backend integration boundary. Empty values keep the current same-origin
# FastAPI implementation; deployments can point the UI at a separate backend.
FRONTEND_API_BASE_URL = os.getenv("CAMPUS_API_BASE_URL", "").strip().rstrip("/")
FRONTEND_WS_BASE_URL = os.getenv("CAMPUS_WS_BASE_URL", "").strip().rstrip("/")
API_CONTRACT_VERSION = "1.0"
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CAMPUS_CORS_ORIGINS", "").split(",")
    if origin.strip()
]


class RuntimeConfig:
    def __init__(self) -> None:
        self.video_source = VIDEO_SOURCE
        self.conf_threshold = CONF_THRESHOLD
        self.crowd_threshold = CROWD_THRESHOLD
        self.fall_ratio_threshold = FALL_RATIO_THRESHOLD
        self.fall_consecutive_frames = FALL_CONSECUTIVE_FRAMES
        self.alarm_cooldown_seconds = ALARM_COOLDOWN_SECONDS
        self.enable_fire_detection = ENABLE_FIRE_DETECTION
        self.fire_conf_threshold = FIRE_CONF_THRESHOLD
        self.fire_alarm_cooldown_seconds = FIRE_ALARM_COOLDOWN_SECONDS

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if value is not None and hasattr(self, key):
                setattr(self, key, self._sanitize(key, value))

    def _sanitize(self, key: str, value):
        if key == "video_source":
            if isinstance(value, str):
                value = value.strip()
                return int(value) if value.isdigit() else value
            return value
        if key in {"conf_threshold", "fire_conf_threshold"}:
            return min(max(float(value), 0.01), 0.99)
        if key == "crowd_threshold":
            return min(max(int(value), 1), 200)
        if key == "fall_ratio_threshold":
            return min(max(float(value), 0.5), 5.0)
        if key == "fall_consecutive_frames":
            return min(max(int(value), 1), 60)
        if key in {"alarm_cooldown_seconds", "fire_alarm_cooldown_seconds"}:
            return min(max(int(value), 0), 3600)
        if key == "enable_fire_detection":
            return bool(value)
        return value

    def to_dict(self) -> dict:
        return {
            "video_source": self.video_source,
            "conf_threshold": self.conf_threshold,
            "crowd_threshold": self.crowd_threshold,
            "fall_ratio_threshold": self.fall_ratio_threshold,
            "fall_consecutive_frames": self.fall_consecutive_frames,
            "alarm_cooldown_seconds": self.alarm_cooldown_seconds,
            "enable_fire_detection": self.enable_fire_detection,
            "fire_conf_threshold": self.fire_conf_threshold,
            "fire_alarm_cooldown_seconds": self.fire_alarm_cooldown_seconds,
        }


runtime_config = RuntimeConfig()
