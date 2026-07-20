"""Enemy field perception unit tests (pure geometry, no game window)."""

import unittest
from dataclasses import dataclass
from unittest.mock import MagicMock

from src.combat.enemy_field import (
    CONF_SCATTER_GATHER,
    CONF_VISION_STEER,
    EnemyField,
    analyze_enemy_field,
    compute_centroid,
    compute_spread,
    feature_enabled,
    read_enemy_field,
    should_gather,
)


@dataclass
class FakeBox:
    x: float
    y: float
    width: float
    height: float


VIEWPORT = FakeBox(0, 0, 1000, 1000)


class TestComputeCentroid(unittest.TestCase):
    def test_empty_returns_none(self):
        self.assertIsNone(compute_centroid([]))
        self.assertIsNone(compute_centroid(None))

    def test_single_box_center(self):
        centroid = compute_centroid([FakeBox(100, 200, 40, 60)])
        self.assertEqual(centroid, (120.0, 230.0))

    def test_two_boxes_average(self):
        boxes = [FakeBox(0, 0, 100, 100), FakeBox(200, 200, 100, 100)]
        centroid = compute_centroid(boxes)
        self.assertEqual(centroid, (150.0, 150.0))

    def test_ignores_non_box_objects(self):
        centroid = compute_centroid([FakeBox(0, 0, 10, 10), object()])
        self.assertEqual(centroid, (5.0, 5.0))


class TestComputeSpread(unittest.TestCase):
    def test_zero_when_no_boxes(self):
        self.assertEqual(compute_spread([], (0, 0), 100), 0.0)

    def test_zero_when_scale_zero(self):
        self.assertEqual(compute_spread([FakeBox(0, 0, 10, 10)], (5, 5), 0), 0.0)

    def test_tight_cluster_low_spread(self):
        boxes = [FakeBox(490, 490, 20, 20), FakeBox(500, 500, 20, 20)]
        centroid = compute_centroid(boxes)
        spread = compute_spread(boxes, centroid, 1000)
        self.assertLess(spread, 0.02)

    def test_scattered_cluster_high_spread(self):
        boxes = [FakeBox(0, 0, 20, 20), FakeBox(980, 980, 20, 20)]
        centroid = compute_centroid(boxes)
        spread = compute_spread(boxes, centroid, 1000)
        self.assertGreater(spread, 0.3)


class TestShouldGather(unittest.TestCase):
    def test_no_enemies_never_gathers(self):
        self.assertFalse(should_gather(0, 0.9))

    def test_single_enemy_triggers_gather(self):
        self.assertTrue(should_gather(1, 0.0))

    def test_low_count_trigger_disabled(self):
        self.assertFalse(should_gather(1, 0.0, low_count_trigger=0))

    def test_tight_group_no_gather(self):
        self.assertFalse(should_gather(4, 0.05))

    def test_scattered_group_gathers(self):
        self.assertTrue(should_gather(4, 0.30))


class TestAnalyzeEnemyField(unittest.TestCase):
    def test_no_boxes_available_but_empty(self):
        field = analyze_enemy_field([], VIEWPORT)
        self.assertTrue(field.available)
        self.assertEqual(field.count, 0)
        self.assertFalse(field.scattered)

    def test_centroid_normalised_to_viewport(self):
        boxes = [FakeBox(0, 0, 100, 100)]  # centre at (50, 50)
        field = analyze_enemy_field(boxes, VIEWPORT)
        self.assertAlmostEqual(field.centroid_x, 0.05)
        self.assertAlmostEqual(field.centroid_y, 0.05)

    def test_centroid_clamped_to_unit_range(self):
        boxes = [FakeBox(2000, 2000, 10, 10)]  # far outside viewport
        field = analyze_enemy_field(boxes, VIEWPORT)
        self.assertEqual(field.centroid_x, 1.0)
        self.assertEqual(field.centroid_y, 1.0)

    def test_scattered_flag_set_for_wide_spread(self):
        boxes = [FakeBox(0, 0, 20, 20), FakeBox(980, 980, 20, 20)]
        field = analyze_enemy_field(boxes, VIEWPORT)
        self.assertTrue(field.scattered)

    def test_viewport_offset_accounted(self):
        viewport = FakeBox(100, 100, 1000, 1000)
        boxes = [FakeBox(100, 100, 100, 100)]  # centre (150,150) -> (50,50) in viewport
        field = analyze_enemy_field(boxes, viewport)
        self.assertAlmostEqual(field.centroid_x, 0.05)
        self.assertAlmostEqual(field.centroid_y, 0.05)


class TestFeatureEnabled(unittest.TestCase):
    def test_missing_config_false(self):
        task = MagicMock(spec=[])
        self.assertFalse(feature_enabled(task, CONF_VISION_STEER))

    def test_dict_config_true(self):
        task = MagicMock()
        task.config = {CONF_VISION_STEER: True}
        self.assertTrue(feature_enabled(task, CONF_VISION_STEER))

    def test_dict_config_false(self):
        task = MagicMock()
        task.config = {CONF_VISION_STEER: False}
        self.assertFalse(feature_enabled(task, CONF_VISION_STEER))

    def test_magicmock_config_defaults_false(self):
        """A bare MagicMock config must NOT accidentally enable the feature."""
        task = MagicMock()
        self.assertFalse(feature_enabled(task, CONF_VISION_STEER))


class TestReadEnemyField(unittest.TestCase):
    def _task(self, boxes, config=None):
        task = MagicMock()
        task.config = config or {}
        task.openvino_available = True
        task.main_viewport = VIEWPORT
        task.frame = object()
        task.openvino_detect.return_value = boxes
        return task

    def test_both_features_off_does_not_touch_detector(self):
        task = self._task([FakeBox(0, 0, 10, 10)])
        field = read_enemy_field(task)
        self.assertFalse(field.available)
        task.openvino_detect.assert_not_called()

    def test_detector_unavailable(self):
        task = self._task([], config={CONF_VISION_STEER: True})
        task.openvino_available = False
        field = read_enemy_field(task)
        self.assertFalse(field.available)

    def test_returns_analysis_when_enabled(self):
        boxes = [FakeBox(0, 0, 20, 20), FakeBox(980, 980, 20, 20)]
        task = self._task(boxes, config={CONF_SCATTER_GATHER: True})
        field = read_enemy_field(task)
        self.assertTrue(field.available)
        self.assertEqual(field.count, 2)
        self.assertTrue(field.scattered)

    def test_empty_detection_is_available(self):
        task = self._task([], config={CONF_VISION_STEER: True})
        field = read_enemy_field(task)
        self.assertTrue(field.available)
        self.assertEqual(field.count, 0)

    def test_detect_exception_degrades_to_unavailable(self):
        task = self._task([], config={CONF_VISION_STEER: True})
        task.openvino_detect.side_effect = RuntimeError("boom")
        field = read_enemy_field(task)
        self.assertFalse(field.available)


class TestEnemyFieldUnavailable(unittest.TestCase):
    def test_unavailable_defaults(self):
        field = EnemyField.unavailable()
        self.assertFalse(field.available)
        self.assertEqual(field.count, 0)
        self.assertFalse(field.scattered)


if __name__ == "__main__":
    unittest.main()
