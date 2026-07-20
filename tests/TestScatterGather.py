"""Scatter-triggered gather tactical request unit tests."""

import time
import unittest
from unittest.mock import MagicMock

from src.combat.enemy_field import CONF_SCATTER_GATHER
from src.combat.skill_cooldown import SkillCooldownModel
from src.combat.team_strategies import (
    _find_ready_gather_char,
    maybe_request_scatter_gather,
)


class _Box:
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height


class FakeGatherChar:
    def __init__(self, ready=True, index=1):
        self.index = index
        self.is_dead = False
        self._ready = ready
        self._cooldowns = SkillCooldownModel(now_fn=time.monotonic)

    def gather_ready(self):
        return self._ready


class FakeContext:
    def __init__(self):
        self.routes = []

    def request_route(self, steps, reason=None, until=None, return_to_source=False):
        self.routes.append(
            {"steps": steps, "reason": reason, "return_to_source": return_to_source}
        )


def _task(boxes, enabled=True):
    task = MagicMock()
    task.config = {CONF_SCATTER_GATHER: enabled}
    task.openvino_available = True
    task.main_viewport = _Box(0, 0, 1000, 1000)
    task.frame = object()
    task.openvino_detect.return_value = boxes
    return task


SCATTERED = [_Box(0, 0, 20, 20), _Box(980, 980, 20, 20)]
CLUSTERED = [_Box(490, 490, 20, 20), _Box(500, 500, 20, 20)]


class TestFindReadyGatherChar(unittest.TestCase):
    def test_finds_ready_char(self):
        ready = FakeGatherChar(ready=True)
        self.assertIs(_find_ready_gather_char([ready]), ready)

    def test_skips_not_ready(self):
        not_ready = FakeGatherChar(ready=False)
        self.assertIsNone(_find_ready_gather_char([not_ready]))

    def test_skips_dead(self):
        dead = FakeGatherChar(ready=True)
        dead.is_dead = True
        self.assertIsNone(_find_ready_gather_char([dead]))

    def test_skips_chars_without_gather_ready(self):
        plain = MagicMock(spec=[])  # no gather_ready attribute
        ready = FakeGatherChar(ready=True)
        self.assertIs(_find_ready_gather_char([plain, ready]), ready)


class TestMaybeRequestScatterGather(unittest.TestCase):
    def test_disabled_requests_nothing(self):
        ctx = FakeContext()
        gather = FakeGatherChar(ready=True)
        maybe_request_scatter_gather(ctx, _task(SCATTERED, enabled=False), [gather], None)
        self.assertEqual(ctx.routes, [])

    def test_scattered_with_ready_gather_requests_route(self):
        ctx = FakeContext()
        gather = FakeGatherChar(ready=True)
        maybe_request_scatter_gather(ctx, _task(SCATTERED), [gather], None)
        self.assertEqual(len(ctx.routes), 1)
        self.assertTrue(ctx.routes[0]["return_to_source"])

    def test_clustered_requests_nothing(self):
        ctx = FakeContext()
        gather = FakeGatherChar(ready=True)
        maybe_request_scatter_gather(ctx, _task(CLUSTERED), [gather], None)
        self.assertEqual(ctx.routes, [])

    def test_no_ready_gather_requests_nothing(self):
        ctx = FakeContext()
        gather = FakeGatherChar(ready=False)
        maybe_request_scatter_gather(ctx, _task(SCATTERED), [gather], None)
        self.assertEqual(ctx.routes, [])

    def test_detection_unavailable_requests_nothing(self):
        ctx = FakeContext()
        gather = FakeGatherChar(ready=True)
        task = _task(SCATTERED)
        task.openvino_available = False
        maybe_request_scatter_gather(ctx, task, [gather], None)
        self.assertEqual(ctx.routes, [])

    def test_request_cooldown_prevents_rapid_repeat(self):
        ctx = FakeContext()
        gather = FakeGatherChar(ready=True)
        task = _task(SCATTERED)
        maybe_request_scatter_gather(ctx, task, [gather], None)
        maybe_request_scatter_gather(ctx, task, [gather], None)
        self.assertEqual(len(ctx.routes), 1)

    def test_single_visible_enemy_triggers_gather(self):
        ctx = FakeContext()
        gather = FakeGatherChar(ready=True)
        maybe_request_scatter_gather(ctx, _task([_Box(100, 100, 20, 20)]), [gather], None)
        self.assertEqual(len(ctx.routes), 1)


if __name__ == "__main__":
    unittest.main()
