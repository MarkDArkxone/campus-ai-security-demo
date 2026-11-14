from pathlib import Path

import cv2
import numpy as np

from app.config import FIRE_MODEL_PATH


class FireDetector:
    def __init__(self, conf_threshold: float = 0.4) -> None:
        self.conf_threshold = conf_threshold
        self.model = None
        self.using_yolo = False
        if FIRE_MODEL_PATH and Path(FIRE_MODEL_PATH).exists():
            from ultralytics import YOLO

            self.model = YOLO(FIRE_MODEL_PATH)
            self.using_yolo = True

    def detect(self, frame) -> dict:
        if self.using_yolo and self.model is not None:
            return self._detect_with_yolo(frame)
        return self._detect_with_color_rule(frame)

    def _detect_with_yolo(self, frame) -> dict:
        result = {"has_fire": False, "has_smoke": False, "confidence": 0.0, "boxes": []}
        outputs = self.model.predict(frame, conf=self.conf_threshold, verbose=False)
        if not outputs:
            return result
        names = outputs[0].names
        boxes = outputs[0].boxes
        if boxes is None:
            return result
        for box in boxes:
            cls_id = int(box.cls[0])
            class_name = names.get(cls_id, str(cls_id)).lower()
            confidence = float(box.conf[0])
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
            if "fire" in class_name or "flame" in class_name:
                result["has_fire"] = True
            if "smoke" in class_name:
                result["has_smoke"] = True
            if result["has_fire"] or result["has_smoke"]:
                result["confidence"] = max(result["confidence"], confidence)
                result["boxes"].append({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "label": class_name, "confidence": confidence})
        return result

    def _detect_with_color_rule(self, frame) -> dict:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower1 = np.array([0, 90, 120])
        upper1 = np.array([25, 255, 255])
        lower2 = np.array([160, 80, 120])
        upper2 = np.array([179, 255, 255])
        mask = cv2.inRange(hsv, lower1, upper1) | cv2.inRange(hsv, lower2, upper2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        boxes = []
        total_area = frame.shape[0] * frame.shape[1]
        fire_area = 0
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 500:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            boxes.append({"x1": x, "y1": y, "x2": x + w, "y2": y + h, "label": "fire_rule", "confidence": min(0.95, area / 5000)})
            fire_area += area

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        saturation = hsv[:, :, 1]
        smoke_mask = cv2.inRange(gray, 110, 225) & cv2.inRange(saturation, 0, 55)
        smoke_ratio = float(cv2.countNonZero(smoke_mask)) / float(total_area)

        has_fire = fire_area / total_area > 0.002
        has_smoke = smoke_ratio > 0.18
        confidence = max(min(0.95, fire_area / max(1, total_area) * 20), min(0.85, smoke_ratio * 3))
        return {"has_fire": has_fire, "has_smoke": has_smoke, "confidence": confidence, "boxes": boxes}
