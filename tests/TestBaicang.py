"""白藏(Baicang)自动战斗逻辑单元测试。

使用 mock 隔离键鼠输入，只验证动作选择、调用次数和异常处理。
结构参考 TestCombatPlanner.py 的 TestableChar 模式。
"""

import unittest
from unittest.mock import MagicMock, patch

from src.char.Baicang import Baicang
from src.char.BaseChar import BaseChar, Element
from src.char.CharFactory import char_dict
from src.combat.BaseCombatTask import NotInCombatException
from src.combat.planner import ActionSlot, FieldPreference, Role


class TestableBaicang(Baicang):
    """Baicang 子类：使用假时钟、空 sleep，覆盖所有输入方法。"""

    __test__ = False

    def __init__(self, task=None, index=0, char_id="baicang"):
        if task is None:
            task = MagicMock()
        super().__init__(task, index, char_id=char_id)
        self._fake_time = 0.0
        self._skill_available = False
        self._ultimate_available = False
        self._click_skill_result = True
        self._click_ultimate_result = True
        self._combat_active = True
        self._mock_burst = False
        self.skill_calls = 0
        self.ultimate_calls = 0
        self.check_combat_calls = 0
        self.fallback_calls = 0
        self.switch_calls = 0
        self._skill_available_sequence = None
        self._skill_available_seq_idx = 0

        def mock_click(*args, **kwargs):
            interval = kwargs.get("interval", -1)
            if interval > 0:
                self._fake_time += interval

        self.task.click.side_effect = mock_click

    def _now(self):
        return self._fake_time

    def sleep(self, sec, sleep_check=True):
        self._fake_time += sec

    def skill_available(self, check_color=True):
        if self._skill_available_sequence is not None:
            if self._skill_available_seq_idx < len(self._skill_available_sequence):
                val = self._skill_available_sequence[self._skill_available_seq_idx]
                self._skill_available_seq_idx += 1
                return val
            return False
        return self._skill_available

    def ultimate_available(self, check_color=True):
        return self._ultimate_available

    def click_skill(self, **kwargs):
        self.skill_calls += 1
        return self._click_skill_result

    def click_ultimate(self, **kwargs):
        self.ultimate_calls += 1
        return self._click_ultimate_result

    def check_combat(self):
        self.check_combat_calls += 1
        if not self._combat_active:
            raise NotInCombatException("test: not in combat")

    def continues_right_click(self, duration, interval=0.1, direction_key=None):
        self.fallback_calls += 1
        self._fake_time += duration

    def switch_other_char(self):
        self.switch_calls += 1

    def _perform_burst(self, context=None):
        if self._mock_burst:
            self._fake_time += self.ULT_FIELD_DURATION
            return
        super()._perform_burst(context)


class TestBaicangFactory(unittest.TestCase):
    def test_char_dict_contains_baicang(self):
        self.assertIn("char_baicang", char_dict)

    def test_char_dict_cls_is_baicang(self):
        self.assertIs(char_dict["char_baicang"]["cls"], Baicang)

    def test_char_dict_cn_name(self):
        self.assertEqual(char_dict["char_baicang"]["cn_name"], "白藏")

    def test_char_dict_element_is_red(self):
        self.assertEqual(char_dict["char_baicang"]["element"], Element.RED)

    def test_baicang_is_subclass_of_basechar(self):
        self.assertTrue(issubclass(Baicang, BaseChar))


class TestBaicangRole(unittest.TestCase):
    def setUp(self):
        self.char = TestableBaicang()

    def test_role_is_main_dps(self):
        self.assertEqual(self.char.describe_role().role, Role.MAIN_DPS)

    def test_field_preference_is_main_dps(self):
        self.assertEqual(self.char.describe_role().field_preference, FieldPreference.MAIN_DPS)

    def test_max_field_time_positive(self):
        self.assertGreater(self.char.describe_role().max_field_time, 0)

    def test_combat_start_priority_is_zero(self):
        self.assertEqual(self.char.describe_role().combat_start_priority, 0)


class TestBaicangCombatPlan(unittest.TestCase):
    def setUp(self):
        self.char = TestableBaicang()

    def _first_entry_action(self):
        plan = self.char.combat_plan(None)
        gen = plan.entry()
        return next(gen)

    def test_skill_entry_yielded_first(self):
        self.char._skill_available = True
        self.char._ultimate_available = True
        action = self._first_entry_action()
        self.assertIn("skill", action.name)

    def test_ultimate_yielded_after_skill(self):
        self.char._skill_available = True
        self.char._ultimate_available = True
        self.char._mock_burst = True
        plan = self.char.combat_plan(None)
        gen = plan.entry()
        first = next(gen)
        self.assertIn("skill", first.name)
        second = gen.send(True)
        self.assertIn("ultimate", second.name)

    def test_fallback_dodge_when_both_fail(self):
        self.char._skill_available = False
        self.char._ultimate_available = False
        plan = self.char.combat_plan(None)
        gen = plan.entry()
        first = next(gen)
        self.assertIn("skill", first.name)
        second = gen.send(False)
        self.assertIn("ultimate", second.name)
        third = gen.send(False)
        self.assertEqual(third.name, "baicang_dodge_fallback")

    def test_fallback_dodge_when_skill_fails_and_ultimate_unavailable(self):
        self.char._skill_available = True
        self.char._ultimate_available = False
        self.char._click_skill_result = False
        plan = self.char.combat_plan(None)
        gen = plan.entry()
        first = next(gen)
        self.assertIn("skill", first.name)
        second = gen.send(False)
        self.assertIn("ultimate", second.name)
        third = gen.send(False)
        self.assertEqual(third.name, "baicang_dodge_fallback")

    def test_perform_burst_called_on_ultimate_success(self):
        self.char._skill_available = True
        self.char._ultimate_available = True
        self.char._mock_burst = True
        before_time = self.char._fake_time
        plan = self.char.combat_plan(None)
        gen = plan.entry()
        next(gen)
        gen.send(True)
        with self.assertRaises(StopIteration):
            gen.send(True)
        self.assertGreater(self.char._fake_time, before_time)

    def test_fallback_dodge_not_attract_switching(self):
        plan = self.char.combat_plan(None)
        fallback = [a for a in plan.actions if a.name == "baicang_dodge_fallback"][0]
        self.assertFalse(fallback.priority_ready(None))

    def test_skill_action_has_skill_slot(self):
        plan = self.char.combat_plan(None)
        skill_action = [a for a in plan.actions if "skill" in a.name and "fallback" not in a.name][
            0
        ]
        self.assertEqual(skill_action.slot, ActionSlot.SKILL)

    def test_ultimate_action_has_ultimate_slot(self):
        plan = self.char.combat_plan(None)
        ult_action = [a for a in plan.actions if "ultimate" in a.name][0]
        self.assertEqual(ult_action.slot, ActionSlot.ULTIMATE)

    def test_field_claim_when_ultimate_available(self):
        self.char._ultimate_available = True
        plan = self.char.combat_plan(None)
        self.assertTrue(len(plan.claims) > 0)
        claim = plan.claims[0]
        self.assertIn("burst", claim.reason.lower())

    def test_no_field_claim_when_ultimate_unavailable(self):
        self.char._ultimate_available = False
        plan = self.char.combat_plan(None)
        self.assertEqual(len(plan.claims), 0)


class TestBaicangBurst(unittest.TestCase):
    def setUp(self):
        self.char = TestableBaicang()
        self.char._mock_burst = False
        self.char._ultimate_available = True
        self.char._skill_available = True
        self.char.is_current_char = True
        self.char.is_dead = False

    def test_burst_has_timeout(self):
        self.char.ULT_FIELD_DURATION = 0.05
        self.char._perform_burst(None)

    def test_burst_returns_on_char_switch(self):
        original_burst = self.char._right_click_burst

        def burst_with_switch(duration):
            original_burst(duration)
            self.char.is_current_char = False

        self.char._right_click_burst = burst_with_switch
        self.char.ULT_FIELD_DURATION = 0.05
        self.char._perform_burst(None)

    def test_burst_returns_on_death(self):
        original_burst = self.char._right_click_burst

        def burst_with_death(duration):
            original_burst(duration)
            self.char.is_dead = True

        self.char._right_click_burst = burst_with_death
        self.char.ULT_FIELD_DURATION = 0.05
        self.char._perform_burst(None)

    def test_not_in_combat_stops_burst(self):
        self.char._combat_active = False
        with self.assertRaises(NotInCombatException):
            self.char._perform_burst(None)
        self.char.task.send_key_up.assert_called_with("w")

    def test_direction_key_held_during_burst(self):
        self.char._skill_available = False
        self.char.ULT_FIELD_DURATION = 0.05
        self.char._perform_burst(None)
        self.assertEqual(self.char.task.send_key_down.call_count, 1)
        self.assertEqual(self.char.task.send_key_up.call_count, 1)

    def test_burst_does_not_call_click_skill_directly(self):
        self.char._skill_available = False
        self.char.SECOND_SKILL_MODE = "disabled"
        self.char.ULT_FIELD_DURATION = 0.05
        self.char._perform_burst(None)
        self.assertEqual(self.char.skill_calls, 0)

    def test_right_click_burst_no_direction_key(self):
        self.char._right_click_burst(0.3)
        self.char.task.send_key_down.assert_not_called()
        self.char.task.send_key_up.assert_not_called()


class TestBaicangSecondSkill(unittest.TestCase):
    def setUp(self):
        self.char = TestableBaicang()
        self.char._mock_burst = False
        self.char._ultimate_available = True
        self.char._skill_available = True
        self.char.is_current_char = True
        self.char.is_dead = False
        self.char.SECOND_SKILL_MODE = "execute"
        self.char.SKILL_CHECK_INTERVAL = 0.1

    def test_second_skill_at_most_once(self):
        self.char._skill_available_sequence = [False, True, True, True, True, True, True, True]
        self.char._perform_burst(None)
        self.assertLessEqual(self.char.skill_calls, 1)

    def test_observation_mode_no_click(self):
        self.char.SECOND_SKILL_MODE = "observe"
        self.char._skill_available_sequence = [False, True, True, True, True, True, True]
        self.char._perform_burst(None)
        self.assertEqual(self.char.skill_calls, 0)

    def test_disabled_mode_no_tracking(self):
        self.char.SECOND_SKILL_MODE = "disabled"
        self.char._skill_available_sequence = [False, True, True, True, True, True, True, True]
        self.char._perform_burst(None)
        self.assertEqual(self.char.skill_calls, 0)

    def test_single_frame_glitch_no_trigger(self):
        self.char._skill_available_sequence = [False, True, False, False, False, False, False]
        self.char._perform_burst(None)
        self.assertEqual(self.char.skill_calls, 0)

    def test_streak_reset_on_break(self):
        self.char._skill_available_sequence = [
            False,
            True,
            True,
            False,
            True,
            True,
            True,
            True,
            True,
        ]
        self.char._perform_burst(None)
        self.assertEqual(self.char.skill_calls, 1)

    def test_streak_threshold_triggers_once(self):
        self.char._skill_available_sequence = [
            False,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
            True,
        ]
        self.char._perform_burst(None)
        self.assertEqual(self.char.skill_calls, 1)


class TestBaicangFallbackDodge(unittest.TestCase):
    def setUp(self):
        self.char = TestableBaicang()
        self.char.is_current_char = True
        self.char.is_dead = False

    def test_fallback_returns_true_when_active(self):
        result = self.char._execute_fallback_dodge()
        self.assertTrue(result)

    def test_fallback_calls_continues_right_click(self):
        self.char._execute_fallback_dodge()
        self.assertGreater(self.char.fallback_calls, 0)

    def test_fallback_returns_false_when_dead(self):
        self.char.is_dead = True
        result = self.char._execute_fallback_dodge()
        self.assertFalse(result)
        self.assertEqual(self.char.fallback_calls, 0)

    def test_fallback_returns_false_when_not_current(self):
        self.char.is_current_char = False
        result = self.char._execute_fallback_dodge()
        self.assertFalse(result)
        self.assertEqual(self.char.fallback_calls, 0)


class TestBaicangOnCombatEnd(unittest.TestCase):
    def test_on_combat_end_calls_switch_other_char(self):
        char = TestableBaicang()
        char.on_combat_end([])
        self.assertEqual(char.switch_calls, 1)


class TestBaicangNow(unittest.TestCase):
    def test_now_returns_time(self):
        char = Baicang.__new__(Baicang)
        with patch("src.char.Baicang.time.monotonic", return_value=42.5):
            self.assertEqual(char._now(), 42.5)

    def test_now_is_patchable(self):
        char = TestableBaicang()
        char._fake_time = 99.0
        self.assertEqual(char._now(), 99.0)


if __name__ == "__main__":
    unittest.main()
