import math
import time

import cv2


class YoloPersonDetector:
    """YOLOv8 person detector with a built-in mock fallback.

    The demo must keep running even when the model file cannot be loaded, so
    any loading or inference error switches the detector to deterministic mock
    boxes that are good enough for classroom demonstrations.
    """

    def __init__(self, model_name: str, conf_threshold: float = 0.4) -> None:
        self.model_name = model_name
        self.conf_threshold = conf_threshold
        self.model = None
        self.mock_mode = False
        self.last_error: str | None = None
        try:
            from ultralytics import YOLO

            self.model = YOLO(model_name)
        except Exception as exc:
            self.mock_mode = True
            self.last_error = str(exc)

    def set_conf_threshold(self, conf_threshold: float) -> None:
        self.conf_threshold = conf_threshold

    def detect(self, frame):
        if self.mock_mode or self.model is None:
            return self._mock_detect(frame)
        try:
            return self._detect_with_yolo(frame)
        except Exception as exc:
            self.mock_mode = True
            self.last_error = str(exc)
            return self._mock_detect(frame)

    def _detect_with_yolo(self, frame):
        results = self.model.predict(frame, conf=self.conf_threshold, verbose=False)
        persons = []
        annotated = frame.copy()

        if not results:
            return persons, annotated

        result = results[0]
        names = result.names
        if result.boxes is None:
            return persons, annotated

        for box in result.boxes:
            cls_id = int(box.cls[0])
            class_name = names.get(cls_id, str(cls_id))
            confidence = float(box.conf[0])
            if class_name != "person":
                continue
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
            persons.append(self._person(x1, y1, x2, y2, confidence))
            self._draw_person(annotated, persons[-1], "person")

        return persons, annotated

    def _mock_detect(self, frame):
        annotated = frame.copy()
        h, w = frame.shape[:2]
        tick = time.time()
        persons = []

        # Six people appear periodically so crowd gathering can be demonstrated.
        crowd_count = 6 if int(tick / 8) % 2 == 0 else 3
        for i in range(crowd_count):
            x = int(90 + i * min(95, w / 9) + math.sin(tick + i) * 18)
            y = int(150 + (i % 2) * 95 + math.cos(tick * 0.8 + i) * 12)
            bw, bh = 46, 112
            if i == 0:
                # The first mock person crosses the default electronic fence.
                x = int(130 + (math.sin(tick / 2) + 1) * 170)
                y = 190
            if i == 1 and int(tick / 12) % 2 == 0:
                # A wide box periodically triggers the fall rule.
                bw, bh = 142, 72
            x1 = max(0, x)
            y1 = max(96, y)
            x2 = min(w - 1, x + bw)
            y2 = min(h - 1, y + bh)
            persons.append(self._person(x1, y1, x2, y2, 0.86))

        for person in persons:
            self._draw_person(annotated, person, "mock person")

        cv2.putText(
            annotated,
            "MOCK YOLO MODE",
            (18, max(118, h - 78)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (0, 220, 255),
            2,
            cv2.LINE_AA,
        )
        return persons, annotated

    def _person(self, x1, y1, x2, y2, confidence):
        return {
            "x1": int(x1),
            "y1": int(y1),
            "x2": int(x2),
            "y2": int(y2),
            "confidence": float(confidence),
            "class_name": "person",
            "center_x": int((x1 + x2) / 2),
            "center_y": int((y1 + y2) / 2),
        }

    def _draw_person(self, frame, person: dict, label_prefix: str) -> None:
        color = (0, 220, 120)
        x1, y1, x2, y2 = person["x1"], person["y1"], person["x2"], person["y2"]
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.circle(frame, (person["center_x"], person["center_y"]), 4, color, -1)
        label = f"{label_prefix} {person['confidence']:.2f}"
        cv2.putText(frame, label, (x1, max(24, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)
