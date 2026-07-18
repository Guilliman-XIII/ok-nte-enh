"""深渊固定队伍的真实 CombatPlanner 协作测试。"""

import unittest

from src.char.Baicang import Baicang
from src.char.BaseChar import Element
from src.char.CharFactory import char_dict
from src.char.Chiz import Chiz
from src.char.custom.CustomCharManager import CustomCharManager
from src.char.Daphneel import Daphneel
from src.char.Hania import Hania
from src.char.Jiuyuan import Jiuyuan
from src.char.Sakiri import Sakiri
from src.char.Yi import Yi
from src.char.Zero import Zero
from src.combat.planner import ActionSlot, CombatPlanner, FieldPreference


class FakeTask:
    def __init__(self):
        self.chars = []
        self.cycle_full = False

    def find_element_reaction_target(self, source_char):
        return None

    def time_elapsed_accounting_for_freeze(self, start, intro_motion_freeze=False):
        return 999

    def is_cycle_full(self):
        return self.cycle_full

    def wait_until(self, predicate, **kwargs):
        return predicate()


def make_team_char(task, char_cls, index, trace):
    char = char_cls(task, index, char_id=f"char_{index}")
    char.char_name = char_cls.__name__
    char.is_current_char = False
    char.is_dead = False
    char._test_skill_ready = True
    char._test_ultimate_ready = True
    char._last_skill_kwargs = {}

    def skill_available(*args, **kwargs):
        return char._test_skill_ready

    def ultimate_available(*args, **kwargs):
        return char._test_ultimate_ready

    def click_skill(*args, **kwargs):
        char._last_skill_kwargs = kwargs
        trace.append((char.name, "E"))
        was_ready = char._test_skill_ready
        char._test_skill_ready = False
        if isinstance(char, Zero) and was_ready:
            task.cycle_full = True
        return was_ready

    def click_ultimate(*args, **kwargs):
        trace.append((char.name, "Q"))
        was_ready = char._test_ultimate_ready
        char._test_ultimate_ready = False
        return was_ready

    char.skill_available = skill_available
    char.ultimate_available = ultimate_available
    char.click_skill = click_skill
    char.click_ultimate = click_ultimate
    char.sleep = lambda *args, **kwargs: None
    char.check_combat = lambda: None
    if isinstance(char, (Baicang, Daphneel)):
        char._perform_burst = lambda *args, **kwargs: trace.append((char.name, "BURST"))
    if isinstance(char, Chiz):
        char.perform_in_ult = lambda *args, **kwargs: trace.append((char.name, "BURST")) or True
    return char


class TestBaicangAbyssTeam(unittest.TestCase):
    def setUp(self):
        self.trace = []
        self.task = FakeTask()
        self.sakiri = make_team_char(self.task, Sakiri, 0, self.trace)
        self.hania = make_team_char(self.task, Hania, 1, self.trace)
        self.daphneel = make_team_char(self.task, Daphneel, 2, self.trace)
        self.baicang = make_team_char(self.task, Baicang, 3, self.trace)
        self.task.chars = [self.sakiri, self.hania, self.daphneel, self.baicang]
        self.planner = CombatPlanner(self.task)
        self.planner.reset(self.task.chars)

    def _perform_and_switch(self, current):
        current.is_current_char = True
        self.planner.perform_current_char(current)
        return self._switch_only(current)

    def _switch_only(self, current):
        decision = self.planner.decide_switch(current)
        current.is_current_char = False
        decision.target.is_current_char = True
        self.planner.record_switch(decision.target)
        return decision.target

    def test_complete_team_starts_with_sakiri(self):
        decision = self.planner.decide_combat_start_char(self.baicang)

        self.assertIs(decision.target, self.sakiri)

    def test_sakiri_is_opener_only_in_baicang_abyss_team(self):
        profile = self.sakiri.describe_role()

        self.assertEqual(profile.field_preference, FieldPreference.SETUP_ONLY)
        self.assertEqual(profile.max_field_time, 0)

    def test_sakiri_holds_grouping_skill_and_waits_for_settle(self):
        self._perform_and_switch(self.sakiri)

        self.assertEqual(Sakiri.SKILL_SETTLE_DURATION, 1.2)
        self.assertEqual(
            self.sakiri._last_skill_kwargs["down_time"],
            Sakiri.SKILL_HOLD_DURATION,
        )
        self.assertEqual(
            self.sakiri._last_skill_kwargs["post_sleep"],
            Sakiri.SKILL_SETTLE_DURATION,
        )

    def test_sakiri_actions_are_hidden_after_opener(self):
        current = self.sakiri
        current = self._perform_and_switch(current)
        current = self._perform_and_switch(current)
        current = self._perform_and_switch(current)
        self.assertIs(current, self.baicang)

        context = self.planner.context_for(self.sakiri)
        actions = self.sakiri.combat_plan(context).actions

        self.assertFalse(
            next(action for action in actions if action.slot == ActionSlot.SKILL).can_execute(
                context
            )
        )
        self.assertFalse(
            next(action for action in actions if action.slot == ActionSlot.ULTIMATE).can_execute(
                context
            )
        )

    def test_opener_routes_to_baicang_through_supports(self):
        current = self.sakiri
        current = self._perform_and_switch(current)
        self.assertIs(current, self.hania)

        current = self._perform_and_switch(current)
        self.assertIs(current, self.daphneel)

        current = self._perform_and_switch(current)
        self.assertIs(current, self.baicang)
        self.assertEqual(
            self.trace,
            [
                ("Sakiri", "E"),
                ("Hania", "Q"),
                ("Hania", "E"),
                ("Daphneel", "E"),
                ("Daphneel", "Q"),
                ("Daphneel", "BURST"),
            ],
        )

    def test_hania_ultimate_is_optional_in_opener(self):
        self.hania._test_ultimate_ready = False

        current = self._perform_and_switch(self.sakiri)
        current = self._perform_and_switch(current)

        self.assertIs(current, self.daphneel)
        self.assertNotIn(("Hania", "Q"), self.trace)
        self.assertIn(("Hania", "E"), self.trace)

    def test_failed_support_actions_still_return_to_baicang(self):
        for char in (self.sakiri, self.hania, self.daphneel):
            char._test_skill_ready = False
            char._test_ultimate_ready = False

        current = self._perform_and_switch(self.sakiri)
        current = self._perform_and_switch(current)
        current = self._perform_and_switch(current)

        self.assertIs(current, self.baicang)
        self.assertIsNone(self.planner.state.locked_route)

    def test_hania_returns_to_baicang_while_baicang_skills_are_on_cooldown(self):
        current = self._perform_and_switch(self.sakiri)
        current = self._perform_and_switch(current)
        current = self._perform_and_switch(current)
        self.assertIs(current, self.baicang)

        self.baicang._test_skill_ready = False
        self.baicang._test_ultimate_ready = False
        self.sakiri._test_ultimate_ready = False
        self.daphneel._test_skill_ready = False
        self.daphneel._test_ultimate_ready = False
        self.hania._test_skill_ready = True
        self.hania._test_ultimate_ready = True

        current = self._switch_only(current)
        self.assertIs(current, self.hania)
        current = self._perform_and_switch(current)

        self.assertIs(current, self.baicang)

    def test_other_sakiri_team_keeps_default_start_priority(self):
        self.task.chars = [self.sakiri, self.hania]
        planner = CombatPlanner(self.task)
        planner.reset(self.task.chars)

        decision = planner.decide_combat_start_char(self.hania)

        self.assertIs(decision.target, self.hania)

    def test_opener_deadline_unlocks_route(self):
        self.baicang.ABYSS_OPENER_TIMEOUT = 0

        self.planner.context_for(self.sakiri)
        self.planner.context_for(self.sakiri)

        self.assertIsNone(self.planner.state.locked_route)


class TestChizAbyssTeam(unittest.TestCase):
    def setUp(self):
        self.trace = []
        self.task = FakeTask()
        self.chiz = make_team_char(self.task, Chiz, 0, self.trace)
        self.zero = make_team_char(self.task, Zero, 1, self.trace)
        self.jiuyuan = make_team_char(self.task, Jiuyuan, 2, self.trace)
        self.yi = make_team_char(self.task, Yi, 3, self.trace)
        self.jiuyuan.element = Element.GREEN
        self.yi.element = Element.YELLOW
        self.zero.element = Element.WHITE
        self.chiz.element = Element.WHITE
        self.task.chars = [self.chiz, self.zero, self.jiuyuan, self.yi]
        self.planner = CombatPlanner(self.task)
        self.planner.reset(self.task.chars)

    def _perform_and_switch(self, current):
        current.is_current_char = True
        self.planner.perform_current_char(current)
        return self._switch_only(current)

    def _switch_only(self, current):
        decision = self.planner.decide_switch(current)
        current.is_current_char = False
        decision.target.is_current_char = True
        if decision.has_intro and self._can_record_reaction(current, decision.target):
            self.planner.record_entry_reaction(current, decision.target)
            self.task.cycle_full = False
        self.planner.record_switch(decision.target)
        return decision.target

    def _can_record_reaction(self, source, target):
        ring = (
            Element.WHITE,
            Element.GREEN,
            Element.RED,
            Element.PURPLE,
            Element.BLUE,
            Element.YELLOW,
        )
        source_index = ring.index(source.element)
        target_index = ring.index(target.element)
        return (source_index - target_index) % len(ring) in (1, len(ring) - 1)

    def test_yi_is_registered_as_aspect_setup_role(self):
        self.assertIs(char_dict["char_yi"]["cls"], Yi)
        self.assertEqual(char_dict["char_yi"]["cn_name"], "翳")
        self.assertEqual(char_dict["char_yi"]["element"], Element.YELLOW)
        self.assertEqual(self.yi.describe_role().max_field_time, 0)

    def test_yi_is_exposed_in_character_center_builtin_combos(self):
        combo_ids = {combo_id for _, combo_id in CustomCharManager.iter_builtin_combo_items()}

        self.assertIn("char_yi", combo_ids)

    def test_complete_team_starts_with_jiuyuan(self):
        decision = self.planner.decide_combat_start_char(self.chiz)

        self.assertIs(decision.target, self.jiuyuan)

    def test_other_jiuyuan_team_keeps_default_start_priority(self):
        self.task.chars = [self.jiuyuan, self.zero]
        planner = CombatPlanner(self.task)
        planner.reset(self.task.chars)

        decision = planner.decide_combat_start_char(self.zero)

        self.assertIs(decision.target, self.zero)

    def test_opener_deadline_unlocks_route(self):
        self.chiz.ABYSS_ROUTE_TIMEOUT = 0

        self.planner.context_for(self.jiuyuan)
        self.planner.context_for(self.jiuyuan)

        self.assertIsNone(self.planner.state.locked_route)

    def test_opener_uses_full_ring_to_enter_chiz(self):
        current = self._perform_and_switch(self.jiuyuan)
        self.assertIs(current, self.zero)

        current = self._perform_and_switch(current)
        self.assertIs(current, self.jiuyuan)

        current = self._perform_and_switch(current)
        self.assertIs(current, self.zero)
        self.zero._test_skill_ready = True

        current = self._perform_and_switch(current)
        self.assertIs(current, self.yi)

        current = self._perform_and_switch(current)
        self.assertIs(current, self.chiz)
        self.planner.perform_current_char(current)

        self.assertEqual(
            self.trace,
            [
                ("Jiuyuan", "E"),
                ("Zero", "Q"),
                ("Zero", "E"),
                ("Jiuyuan", "Q"),
                ("Zero", "E"),
                ("Yi", "Q"),
                ("Yi", "E"),
                ("Chiz", "Q"),
                ("Chiz", "BURST"),
            ],
        )

    def test_optional_support_ultimates_do_not_block_opener(self):
        self.zero._test_ultimate_ready = False
        self.yi._test_ultimate_ready = False

        current = self._perform_and_switch(self.jiuyuan)
        current = self._perform_and_switch(current)
        current = self._perform_and_switch(current)
        self.zero._test_skill_ready = True
        current = self._perform_and_switch(current)
        current = self._perform_and_switch(current)

        self.assertIs(current, self.chiz)
        self.assertNotIn(("Yi", "Q"), self.trace)
        self.assertNotIn(("Zero", "Q"), self.trace)

    def test_completed_burst_publishes_and_executes_next_yingxu_cycle(self):
        current = self._perform_and_switch(self.jiuyuan)
        current = self._perform_and_switch(current)
        current = self._perform_and_switch(current)
        self.zero._test_skill_ready = True
        current = self._perform_and_switch(current)
        current = self._perform_and_switch(current)
        self.assertIs(current, self.chiz)

        self.planner.perform_current_char(current)
        self.assertEqual(self.planner.state.locked_route.reason, "Chiz Yingxu abyss cycle")

        self.zero._test_skill_ready = True
        current = self._switch_only(current)
        self.assertIs(current, self.zero)

        current = self._perform_and_switch(current)
        self.assertIs(current, self.jiuyuan)

        current = self._perform_and_switch(current)
        self.assertIs(current, self.zero)
        self.zero._test_skill_ready = True

        current = self._perform_and_switch(current)
        self.assertIs(current, self.yi)
        self.yi._test_ultimate_ready = True
        self.yi._test_skill_ready = True

        current = self._perform_and_switch(current)
        self.assertIs(current, self.chiz)
        self.chiz._test_ultimate_ready = True
        self.planner.perform_current_char(current)

        self.assertEqual(self.trace.count(("Chiz", "BURST")), 2)
        self.assertEqual(self.planner.state.locked_route.reason, "Chiz Yingxu abyss cycle")


class TestChizBurstSafety(unittest.TestCase):
    def test_burst_uses_skill_at_most_once_and_stops_when_switched_out(self):
        task = FakeTask()
        task.box_of_screen = lambda *args, **kwargs: object()
        task.wait_ocr = lambda *args, **kwargs: None
        task.calculate_color_percentage = lambda color, box: (
            0.8 if color is not None and color["g"][0] > 200 else 0.1
        )
        trace = []
        char = Chiz(task, 0, char_id="chiz")
        task.chars = [char]
        char.is_current_char = True
        char.is_dead = False
        now = [0.0]
        attacks = [0]

        char._now = lambda: now[0]
        char.skill_available = lambda *args, **kwargs: True
        char.click_skill = lambda *args, **kwargs: trace.append("E") or True
        char.check_combat = lambda: None
        char.sleep = lambda duration, *args, **kwargs: now.__setitem__(0, now[0] + duration)

        def attack_once():
            attacks[0] += 1
            if attacks[0] == 3:
                char.is_current_char = False

        char.click_with_interval = attack_once
        completed = char.perform_in_ult()

        self.assertEqual(trace, ["E"])
        self.assertEqual(attacks[0], 3)
        self.assertFalse(completed)


if __name__ == "__main__":
    unittest.main()
