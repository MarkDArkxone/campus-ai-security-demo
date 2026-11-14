from collections import defaultdict


class FallRuleState:
    def __init__(self) -> None:
        self._counts = defaultdict(int)

    def reset_missing(self, active_keys: set[str]) -> None:
        for key in list(self._counts.keys()):
            if key not in active_keys:
                self._counts.pop(key, None)

    def update(self, key: str, suspected: bool) -> int:
        if suspected:
            self._counts[key] += 1
        else:
            self._counts[key] = 0
        return self._counts[key]


def check_fence_intrusion(persons: list[dict], fence) -> bool:
    return fence.any_intrusion(persons)


def check_crowd_gathering(persons: list[dict], threshold: int) -> bool:
    return len(persons) >= threshold


def check_fall_suspected(
    persons: list[dict],
    ratio_threshold: float,
    state: FallRuleState,
    consecutive_frames: int = 5,
) -> tuple[bool, dict | None]:
    active_keys = set()
    for person in persons:
        width = max(1, person["x2"] - person["x1"])
        height = max(1, person["y2"] - person["y1"])
        ratio = width / height
        key = f"{person['center_x'] // 40}_{person['center_y'] // 40}"
        active_keys.add(key)
        count = state.update(key, ratio > ratio_threshold)
        if count >= consecutive_frames:
            return True, {**person, "fall_ratio": ratio, "fall_frames": count}

    state.reset_missing(active_keys)
    return False, None
