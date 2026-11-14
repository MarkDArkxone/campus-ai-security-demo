import cv2
import numpy as np

from app.config import DEFAULT_FENCE_POINTS

try:
    import supervision as sv
except Exception:  # pragma: no cover - optional enhancement
    sv = None


class ElectronicFence:
    """Electronic fence powered by Roboflow supervision when available.

    `supervision` is a mature open-source computer-vision toolkit. We use its
    PolygonZone for zone triggering, while keeping the original OpenCV logic as
    a fallback so the demo still runs on machines where the dependency is not
    installed correctly.
    """

    def __init__(self, points=None) -> None:
        self.points = points or DEFAULT_FENCE_POINTS
        self.backend = "opencv"
        self._zone = None
        self._annotator = None
        if sv is not None:
            try:
                self._zone = sv.PolygonZone(
                    polygon=self.contour,
                    triggering_anchors=(sv.Position.CENTER,),
                    require_all_anchors=True,
                )
                self._annotator = sv.PolygonZoneAnnotator(
                    zone=self._zone,
                    color=sv.Color(255, 80, 80),
                    thickness=3,
                    text_scale=0.7,
                    text_thickness=2,
                    opacity=0.18,
                )
                self.backend = "supervision"
            except Exception:
                self._zone = None
                self._annotator = None
                self.backend = "opencv"

    @property
    def contour(self):
        return np.array(self.points, dtype=np.int32)

    def persons_inside(self, persons: list[dict]) -> list[dict]:
        if not persons:
            return []
        if self._zone is not None and sv is not None:
            detections = self._to_supervision_detections(persons)
            mask = self._zone.trigger(detections=detections)
            return [person for person, inside in zip(persons, mask.tolist()) if inside]
        return [person for person in persons if self.contains_person(person)]

    def contains_person(self, person: dict) -> bool:
        point = (float(person["center_x"]), float(person["center_y"]))
        return cv2.pointPolygonTest(self.contour, point, False) >= 0

    def draw(self, frame, alert: bool = False):
        if self._annotator is not None:
            frame = self._annotator.annotate(scene=frame, label="Danger Zone")
            if alert:
                cv2.polylines(frame, [self.contour], True, (0, 0, 255), 5)
            return frame

        overlay = frame.copy()
        color = (0, 0, 255) if alert else (0, 180, 255)
        cv2.fillPoly(overlay, [self.contour], color)
        cv2.addWeighted(overlay, 0.18, frame, 0.82, 0, frame)
        cv2.polylines(frame, [self.contour], True, color, 3)
        cv2.putText(
            frame,
            "Danger Zone",
            tuple(self.contour[0]),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
            cv2.LINE_AA,
        )
        return frame

    def any_intrusion(self, persons: list[dict]) -> bool:
        return bool(self.persons_inside(persons))

    def _to_supervision_detections(self, persons: list[dict]):
        xyxy = np.array([[p["x1"], p["y1"], p["x2"], p["y2"]] for p in persons], dtype=float)
        confidence = np.array([p.get("confidence", 0.0) for p in persons], dtype=float)
        class_id = np.zeros(len(persons), dtype=int)
        return sv.Detections(xyxy=xyxy, confidence=confidence, class_id=class_id)
