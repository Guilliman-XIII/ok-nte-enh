"""Enemy field perception built on top of the existing YOLO/OpenVINO detector.

The detector already returns enemy bounding boxes in screen pixels during combat
(see ``CombatCheck.find_target``). This module turns those boxes into a small,
resolution-independent summary the combat code can act on:

- how many enemies are visible
- where the cluster centre is (normalised 0..1 within the play viewport)
- how scattered the cluster is (mean distance from centre / viewport diagonal)
- whether the field looks scattered enough to justify a gather skill

All geometry helpers are pure (they only read ``x``/``y``/``width``/``height``
attributes) so they can be unit tested without a game window or the detector.

Everything here is an experimental, recording-unverified enhancement. The two
features that consume it (vision-steered rolling and scatter-triggered gather)
are config-gated and default OFF; see ``CONF_VISION_STEER`` / ``CONF_SCATTER_GATHER``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Config keys (single source of truth; AutoCombatTask registers defaults).
CONF_VISION_STEER = "视觉引导翻滚方向"
CONF_SCATTER_GATHER = "怪散自动聚怪"

# Mean distance-from-centre, normalised by viewport diagonal, above which the
# cluster is considered scattered. Needs live tuning; see docs/research/baicang.md.
DEFAULT_SCATTER_RATIO = 0.20


@dataclass(frozen=True)
class EnemyField:
    """Resolution-independent snapshot of visible enemies.

    ``centroid_x``/``centroid_y`` are normalised to 0..1 within the play viewport
    (0.5/0.5 is screen centre). ``spread`` is normalised by the viewport diagonal.
    ``available`` is False when the detector cannot run (e.g. CPU lacks AVX2).
    """

    count: int
    centroid_x: float
    centroid_y: float
    spread: float
    scattered: bool
    available: bool

    @classmethod
    def unavailable(cls) -> "EnemyField":
        return cls(0, 0.5, 0.5, 0.0, False, False)


def feature_enabled(task, key: str) -> bool:
    """Return True only when a config flag is explicitly True.

    Defensive on purpose: a missing config, a non-dict config, or a MagicMock in
    unit tests all resolve to False so experimental features stay default-off.
    """

    config = getattr(task, "config", None)
    if config is None:
        return False
    try:
        return config.get(key, False) is True
    except Exception:
        return False


def _center(box) -> tuple[float, float]:
    return (box.x + box.width / 2.0, box.y + box.height / 2.0)


def _is_box(obj) -> bool:
    return all(hasattr(obj, attr) for attr in ("x", "y", "width", "height"))


def compute_centroid(boxes) -> tuple[float, float] | None:
    """Average centre of all boxes, in absolute screen pixels."""

    valid = [b for b in (boxes or []) if _is_box(b)]
    if not valid:
        return None
    xs, ys = zip(*(_center(b) for b in valid))
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def compute_spread(boxes, centroid, scale: float) -> float:
    """Mean distance of box centres from ``centroid``, normalised by ``scale``.

    ``scale`` is expected to be the viewport diagonal so the result is a
    resolution-independent ratio (0 = perfectly clustered).
    """

    valid = [b for b in (boxes or []) if _is_box(b)]
    if not valid or centroid is None or scale <= 0:
        return 0.0
    cx, cy = centroid
    distances = [math.hypot(_center(b)[0] - cx, _center(b)[1] - cy) for b in valid]
    return (sum(distances) / len(distances)) / scale


def should_gather(
    count: int,
    spread: float,
    scatter_ratio: float = DEFAULT_SCATTER_RATIO,
    low_count_trigger: int = 1,
) -> bool:
    """Decide whether the field warrants a gather skill.

    Mirrors the user's heuristic: gather when the pack is spread out, or when
    only a single enemy is visible (the rest were likely knocked off-screen).
    ``count <= 0`` never gathers (nothing to pull, or between waves).
    """

    if count <= 0:
        return False
    if low_count_trigger and count <= low_count_trigger:
        return True
    return spread >= scatter_ratio


def analyze_enemy_field(
    boxes,
    viewport,
    scatter_ratio: float = DEFAULT_SCATTER_RATIO,
    low_count_trigger: int = 1,
) -> EnemyField:
    """Summarise detector boxes relative to the play ``viewport`` box.

    ``viewport`` must expose ``x``/``y``/``width``/``height`` in absolute pixels
    (e.g. ``task.main_viewport``). The returned centroid is normalised to 0..1
    within the viewport and clamped, so steering math is resolution-independent.
    """

    valid = [b for b in (boxes or []) if _is_box(b)]
    centroid = compute_centroid(valid)
    if centroid is None:
        return EnemyField(0, 0.5, 0.5, 0.0, False, True)

    vw = float(getattr(viewport, "width", 0) or 0)
    vh = float(getattr(viewport, "height", 0) or 0)
    vx = float(getattr(viewport, "x", 0) or 0)
    vy = float(getattr(viewport, "y", 0) or 0)
    diag = math.hypot(vw, vh)

    norm_cx = (centroid[0] - vx) / vw if vw > 0 else 0.5
    norm_cy = (centroid[1] - vy) / vh if vh > 0 else 0.5
    norm_cx = min(1.0, max(0.0, norm_cx))
    norm_cy = min(1.0, max(0.0, norm_cy))

    spread = compute_spread(valid, centroid, diag)
    count = len(valid)
    scattered = should_gather(count, spread, scatter_ratio, low_count_trigger)
    return EnemyField(count, norm_cx, norm_cy, spread, scattered, True)


def read_enemy_field(
    task,
    scatter_ratio: float = DEFAULT_SCATTER_RATIO,
    threshold: float = 0.6,
    low_count_trigger: int = 1,
) -> EnemyField:
    """Non-blocking read of the latest enemy detection, summarised.

    Uses ``sync=False`` so it returns the detector's most recent cached result
    instead of stalling the combat loop. Any failure degrades to ``unavailable``
    so callers fall back to their existing behaviour.
    """

    if not feature_enabled(task, CONF_VISION_STEER) and not feature_enabled(
        task, CONF_SCATTER_GATHER
    ):
        # Neither consumer is on; avoid touching the detector at all.
        return EnemyField.unavailable()
    if not getattr(task, "openvino_available", False):
        return EnemyField.unavailable()
    viewport = getattr(task, "main_viewport", None)
    if viewport is None or not _is_box(viewport):
        return EnemyField.unavailable()
    try:
        boxes = task.openvino_detect(
            frame=task.frame, sync=False, box=viewport, threshold=threshold
        )
    except Exception:
        return EnemyField.unavailable()
    if not boxes or not isinstance(boxes, (list, tuple)):
        return EnemyField(0, 0.5, 0.5, 0.0, False, True)
    return analyze_enemy_field(boxes, viewport, scatter_ratio, low_count_trigger)
