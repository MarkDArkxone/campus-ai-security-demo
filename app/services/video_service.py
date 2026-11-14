import asyncio
import os
import platform
import threading
import time
from typing import Any

import cv2
import numpy as np

from app.alarm_manager import alarm_manager
from app.config import MODEL_NAME, runtime_config
from app.detector.fence import ElectronicFence
from app.detector.fire_detector import FireDetector
from app.detector.rules import FallRuleState, check_crowd_gathering, check_fall_suspected, check_fence_intrusion
from app.detector.yolo_detector import YoloPersonDetector


class VideoService:
    def __init__(self) -> None:
        self.detector: YoloPersonDetector | None = None
        self.fire_detector: FireDetector | None = None
        self.fence = ElectronicFence()
        self.fall_state = FallRuleState()
        self.capture: cv2.VideoCapture | None = None
        self.running = False
        self.thread: threading.Thread | None = None
        self.lock = threading.Lock()
        self.latest_frame: bytes | None = None
        self.latest_raw_frame = None
        self.last_error: str | None = None
        self.last_alarm_text = ""
        self.started_at: float | None = None
        self.current_person_count = 0
        self.mock_video_mode = False
        self._state_lock = threading.Lock()

    def _normalize_source(self, source: Any):
        if isinstance(source, str) and source.isdigit():
            return int(source)
        return source

    def status(self) -> dict:
        return {
            "running": self.running,
            "video_source": runtime_config.video_source,
            "started_at": self.started_at,
            "last_error": self.last_error,
            "current_person_count": self.current_person_count,
            "mock_video_mode": self.mock_video_mode,
            "fence_backend": self.fence.backend,
            "config": runtime_config.to_dict(),
        }

    def start(self) -> bool:
        with self._state_lock:
            if self.running and self.thread and self.thread.is_alive():
                return True
            self.running = True
            self.mock_video_mode = False
            self.last_error = None
            self.started_at = time.time()
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
        return True

    def stop(self) -> None:
        with self._state_lock:
            self.running = False
            thread = self.thread
        if thread and thread.is_alive():
            thread.join(timeout=2)
        with self._state_lock:
            self._release_capture()
            self.thread = None
            self.started_at = None
            self.mock_video_mode = False

    def _release_capture(self) -> None:
        if self.capture is not None:
            self.capture.release()
            self.capture = None

    def _ensure_detectors(self) -> None:
        if self.detector is None:
            self.detector = YoloPersonDetector(MODEL_NAME, runtime_config.conf_threshold)
        else:
            self.detector.set_conf_threshold(runtime_config.conf_threshold)
        if self.fire_detector is None:
            self.fire_detector = FireDetector(runtime_config.fire_conf_threshold)
        else:
            self.fire_detector.conf_threshold = runtime_config.fire_conf_threshold

    def _open_capture(self) -> bool:
        self._release_capture()
        source = self._normalize_source(runtime_config.video_source)
        if isinstance(source, str) and not os.path.exists(source):
            self.last_error = f"Video file does not exist: {source}"
            self.mock_video_mode = True
            return False
        if isinstance(source, int) and platform.system().lower() == "windows":
            self.capture = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        else:
            self.capture = cv2.VideoCapture(source)
        if not self.capture.isOpened():
            self.last_error = f"Cannot open video source: {source}"
            self.mock_video_mode = True
            return False
        return True

    def _run_loop(self) -> None:
        self._ensure_detectors()
        capture_opened = self._open_capture()
        while self.running:
            if capture_opened and self.capture is not None:
                ok, frame = self.capture.read()
                if not ok:
                    source = self._normalize_source(runtime_config.video_source)
                    if isinstance(source, str):
                        self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    self.last_error = "Failed to read camera frame, switched to mock video"
                    self.mock_video_mode = True
                    capture_opened = False
                    frame = self._create_mock_frame()
            else:
                frame = self._create_mock_frame()
                time.sleep(0.06)
            try:
                processed = self._process_frame(frame)
                self._store_frame(processed)
            except Exception as exc:
                self.last_error = str(exc)
                self._set_placeholder_frame(f"Detection error: {exc}")
                time.sleep(0.5)
        self._release_capture()

    def _process_frame(self, frame):
        assert self.detector is not None
        if self.mock_video_mode and hasattr(self.detector, "mock_mode"):
            self.detector.mock_mode = True
        persons, annotated = self.detector.detect(frame)
        self.current_person_count = len(persons)

        fence_alarm = check_fence_intrusion(persons, self.fence)
        crowd_alarm = check_crowd_gathering(persons, runtime_config.crowd_threshold)
        fall_alarm, fall_person = check_fall_suspected(
            persons,
            runtime_config.fall_ratio_threshold,
            self.fall_state,
            runtime_config.fall_consecutive_frames,
        )

        self.fence.draw(annotated, fence_alarm)
        alarm_texts = []

        if fence_alarm:
            alarm_texts.append("Fence intrusion")
            alarm_manager.create_alarm_from_thread(
                "fence_intrusion",
                "high",
                "Person entered electronic fence danger zone",
                annotated.copy(),
                len(persons),
                max((p["confidence"] for p in persons), default=None),
                "Teaching Building",
            )

        if crowd_alarm:
            alarm_texts.append("Crowd gathering")
            alarm_manager.create_alarm_from_thread(
                "crowd_gathering",
                "medium",
                f"Crowd gathering detected, persons={len(persons)}, threshold={runtime_config.crowd_threshold}",
                annotated.copy(),
                len(persons),
                max((p["confidence"] for p in persons), default=None),
                "Campus Area",
            )

        if fall_alarm and fall_person:
            alarm_texts.append("Fall suspected")
            cv2.rectangle(annotated, (fall_person["x1"], fall_person["y1"]), (fall_person["x2"], fall_person["y2"]), (0, 0, 255), 3)
            alarm_manager.create_alarm_from_thread(
                "fall_suspected",
                "high",
                "Suspected fall posture detected, manual review required",
                annotated.copy(),
                len(persons),
                fall_person.get("confidence"),
                "Campus Area",
            )

        if runtime_config.enable_fire_detection and self.fire_detector is not None:
            fire_result = self.fire_detector.detect(frame)
            self._draw_fire_result(annotated, fire_result)
            if fire_result["has_fire"]:
                alarm_texts.append("Fire")
                alarm_manager.create_alarm_from_thread(
                    "fire_detected",
                    "high",
                    "Video fire detection warning",
                    annotated.copy(),
                    len(persons),
                    fire_result["confidence"],
                    "Canteen",
                    runtime_config.fire_alarm_cooldown_seconds,
                )
            if fire_result["has_smoke"]:
                alarm_texts.append("Smoke")
                alarm_manager.create_alarm_from_thread(
                    "smoke_detected",
                    "medium",
                    "Video smoke detection warning",
                    annotated.copy(),
                    len(persons),
                    fire_result["confidence"],
                    "Canteen",
                    runtime_config.fire_alarm_cooldown_seconds,
                )
            if fire_result["has_fire"] or fire_result["has_smoke"]:
                try:
                    from app.services.sensor_service import sensor_simulator

                    if sensor_simulator.has_recent_smoke_abnormal():
                        alarm_manager.create_alarm_from_thread(
                            "fire_risk_high",
                            "high",
                            "Video smoke/fire and smoke sensor abnormal at the same time",
                            annotated.copy(),
                            len(persons),
                            fire_result["confidence"],
                            "Canteen",
                            runtime_config.fire_alarm_cooldown_seconds,
                        )
                except Exception:
                    pass

        self.last_alarm_text = " | ".join(alarm_texts)
        self._draw_hud(annotated, len(persons), self.last_alarm_text)
        return annotated

    def _draw_fire_result(self, frame, result: dict) -> None:
        for box in result.get("boxes", []):
            color = (0, 80, 255)
            cv2.rectangle(frame, (box["x1"], box["y1"]), (box["x2"], box["y2"]), color, 2)
            cv2.putText(frame, box["label"], (box["x1"], max(18, box["y1"] - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        y = 120
        if result.get("has_fire"):
            cv2.putText(frame, "FIRE WARNING", (18, y), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 80, 255), 3)
            y += 34
        if result.get("has_smoke"):
            cv2.putText(frame, "SMOKE WARNING", (18, y), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (80, 220, 255), 3)

    def _draw_hud(self, frame, person_count: int, alarm_text: str) -> None:
        h, w = frame.shape[:2]
        cv2.rectangle(frame, (0, 0), (w, 92), (8, 18, 32), -1)
        cv2.putText(frame, "Campus AI Security Demo", (18, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2)
        cv2.putText(frame, f"Status: RUNNING | Persons: {person_count}", (18, 66), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (120, 230, 255), 2)
        if alarm_text:
            cv2.rectangle(frame, (0, h - 48), (w, h), (0, 0, 160), -1)
            cv2.putText(frame, f"ALARM: {alarm_text}", (18, h - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)

    def _store_frame(self, frame) -> None:
        try:
            ok, buffer = cv2.imencode(".jpg", frame)
        except Exception as exc:
            self.last_error = f"JPEG encode failed: {exc}"
            return
        if not ok:
            self.last_error = "JPEG encode failed"
            return
        with self.lock:
            self.latest_raw_frame = frame
            self.latest_frame = buffer.tobytes()

    def _set_placeholder_frame(self, text: str) -> None:
        frame = np.zeros((540, 960, 3), dtype=np.uint8)
        frame[:] = (12, 24, 38)
        cv2.putText(frame, "Campus AI Security Demo", (60, 210), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
        cv2.putText(frame, text, (60, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80, 220, 255), 2)
        self._store_frame(frame)

    def _create_mock_frame(self):
        h, w = 540, 960
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:] = (18, 34, 46)
        cv2.rectangle(frame, (55, 130), (330, 300), (42, 78, 92), -1)
        cv2.rectangle(frame, (610, 95), (875, 270), (36, 72, 58), -1)
        cv2.rectangle(frame, (360, 340), (585, 490), (64, 54, 40), -1)
        cv2.ellipse(frame, (745, 395), (165, 82), 0, 0, 360, (30, 82, 50), -1)
        cv2.putText(frame, "Teaching Building", (80, 216), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (210, 235, 245), 2)
        cv2.putText(frame, "Dormitory", (665, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (210, 235, 245), 2)
        cv2.putText(frame, "Canteen", (420, 422), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (210, 235, 245), 2)
        cv2.putText(frame, "Playground", (670, 404), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (210, 235, 245), 2)
        cv2.line(frame, (0, 322), (960, 322), (74, 112, 126), 3)
        cv2.putText(frame, "MOCK CAMERA MODE - no physical camera required", (18, 520), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 255), 2)
        return frame

    async def mjpeg_generator(self):
        if self.latest_frame is None:
            self._set_placeholder_frame("Click start detection")
        try:
            while True:
                with self.lock:
                    frame = self.latest_frame
                if frame is None:
                    await asyncio.sleep(0.05)
                    continue
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                await asyncio.sleep(0.04)
        except asyncio.CancelledError:
            return


video_service = VideoService()
