import unittest
from unittest.mock import Mock, PropertyMock, patch

import numpy as np

from src.char.BaseChar import Element
from src.combat.BaseCombatTask import BaseCombatTask, VisibleTeamMatch


class TestTeamPresetGuard(unittest.TestCase):
    def _task(self):
        task = object.__new__(BaseCombatTask)
        task._strict_team_last_error = ""
        task.log_error = Mock()
        task.log_info = Mock()
        return task

    @staticmethod
    def _preset():
        return {
            "preset_id": "team_a",
            "name": "Team A",
            "slots": [
                {"char_id": f"char_{index}", "combo_id": ""} for index in range(4)
            ],
        }

    @staticmethod
    def _manager():
        manager = Mock()
        manager.get_character_info_by_id.side_effect = lambda char_id: (
            {"char_name": char_id} if char_id else None
        )
        return manager

    @staticmethod
    def _visible_match(preset_id="team_a", ids=None):
        ids = tuple(ids or ("char_0", "char_1", "char_2", "char_3"))
        return VisibleTeamMatch(
            preset_id=preset_id,
            preset_name=preset_id,
            char_ids=ids,
            slots=tuple({"char_id": char_id, "combo_id": ""} for char_id in ids),
        )

    def test_exact_four_slot_match_passes(self):
        task = self._task()
        manager = self._manager()
        manager.match_feature.side_effect = [
            (True, f"char_{index}", 0.95) for index in range(4)
        ]
        feature = np.ones((8, 8, 3), dtype=np.uint8)

        with (
            patch.object(
                BaseCombatTask,
                "frame",
                new_callable=PropertyMock,
                return_value=np.zeros((32, 32, 3), dtype=np.uint8),
            ),
            patch(
                "src.combat.BaseCombatTask.get_char_feature_by_pos",
                return_value=(feature, 1920, 1080),
            ),
        ):
            verified = task._verify_armed_team(self._preset(), 4, manager)

        self.assertTrue(verified)
        self.assertEqual(manager.match_feature.call_count, 4)
        task.log_error.assert_not_called()
        task.log_info.assert_called_once()

    def test_wrong_slot_fails_closed_and_deduplicates_notification(self):
        task = self._task()
        manager = self._manager()
        manager.match_feature.return_value = (True, "wrong_char", 0.91)
        feature = np.ones((8, 8, 3), dtype=np.uint8)

        with (
            patch.object(
                BaseCombatTask,
                "frame",
                new_callable=PropertyMock,
                return_value=np.zeros((32, 32, 3), dtype=np.uint8),
            ),
            patch(
                "src.combat.BaseCombatTask.get_char_feature_by_pos",
                return_value=(feature, 1920, 1080),
            ),
        ):
            first = task._verify_armed_team(self._preset(), 4, manager)
            second = task._verify_armed_team(self._preset(), 4, manager)

        self.assertFalse(first)
        self.assertFalse(second)
        task.log_error.assert_called_once()
        self.assertTrue(task.log_error.call_args.kwargs["notify"])

    def test_incomplete_party_fails_before_visual_matching(self):
        task = self._task()
        manager = self._manager()

        verified = task._verify_armed_team(self._preset(), 3, manager)

        self.assertFalse(verified)
        manager.match_feature.assert_not_called()
        task.log_error.assert_called_once()

    def test_visible_auto_match_remaps_saved_combo_to_actual_slot_order(self):
        task = self._task()
        manager = self._manager()
        ids = ("char_2", "char_0", "char_3", "char_1")
        manager.match_feature.side_effect = [(True, char_id, 0.95) for char_id in ids]
        manager.match_team_preset.return_value = "team_a"
        manager.get_team_preset.return_value = {
            "preset_id": "team_a",
            "name": "Team A",
            "slots": [
                {"char_id": f"char_{index}", "combo_id": f"combo_{index}"}
                for index in range(4)
            ],
        }
        feature = np.ones((8, 8, 3), dtype=np.uint8)

        with (
            patch.object(
                BaseCombatTask,
                "frame",
                new_callable=PropertyMock,
                return_value=np.zeros((32, 32, 3), dtype=np.uint8),
            ),
            patch(
                "src.combat.BaseCombatTask.get_char_feature_by_pos",
                return_value=(feature, 1920, 1080),
            ),
        ):
            match = task._match_visible_team_preset(4, manager)

        self.assertEqual(match.char_ids, ids)
        self.assertEqual(
            match.slots,
            tuple({"char_id": char_id, "combo_id": f"combo_{char_id[-1]}"} for char_id in ids),
        )

    def test_auto_handoff_requires_two_identical_complete_frames(self):
        task = self._task()
        previous = self._visible_match("upper")
        following = self._visible_match("lower", ("char_3", "char_2", "char_1", "char_0"))
        task._team_binding = previous
        task._pending_team_binding = None
        task._team_binding_last_check = 0.0
        task._in_animation = False
        task.in_team = Mock(return_value=(True, 0, 4))
        task._match_visible_team_preset = Mock(side_effect=[following, following])
        task._is_auto_team_selection_enabled = Mock(return_value=True)
        task.load_chars = Mock(return_value=True)

        self.assertFalse(task.ensure_team_binding(force=True))
        task.load_chars.assert_not_called()
        self.assertEqual(task._pending_team_binding, following)

        self.assertFalse(task.ensure_team_binding(force=True))
        task.load_chars.assert_called_once_with(visible_match=following)

    def test_manual_handoff_clears_old_routes_without_rebinding(self):
        task = self._task()
        task._team_binding = self._visible_match("upper")
        task._pending_team_binding = None
        task._team_binding_last_check = 0.0
        task._in_animation = False
        task.in_team = Mock(return_value=(True, 0, 4))
        task._match_visible_team_preset = Mock(
            return_value=self._visible_match("lower", ("char_3", "char_2", "char_1", "char_0"))
        )
        task._is_auto_team_selection_enabled = Mock(return_value=False)
        task.combat_planner = Mock()

        self.assertFalse(task.ensure_team_binding(force=True))
        task.combat_planner.reset.assert_called_once_with([])

    def _load_task(self):
        task = object.__new__(BaseCombatTask)
        task.load_hotkey = Mock()
        task.in_team = Mock(return_value=(True, 0, 4))
        task.log_info = Mock()
        task.clear_element_reactions = Mock()
        task._verify_armed_team = Mock()
        task._do_load_char = Mock()
        task.load_chars_element = Mock(return_value={})
        task.info_set = Mock()
        task.info_add_to_list = Mock()
        task._apply_sound_config = Mock()
        task.combat_planner = Mock()
        task.chars = []
        task.active_team_preset_id = ""
        return task

    def test_load_chars_never_falls_back_when_armed_verification_fails(self):
        task = self._load_task()
        task._verify_armed_team.return_value = False
        manager = Mock()
        manager.get_fixed_team.return_value = {"enabled": False, "slots": []}
        manager.get_armed_team_preset.return_value = self._preset()

        with patch("src.combat.BaseCombatTask.CustomCharManager", return_value=manager):
            loaded = BaseCombatTask.load_chars(task)

        self.assertFalse(loaded)
        task._do_load_char.assert_not_called()
        manager.consume_armed_team_preset.assert_not_called()

    def test_load_chars_consumes_arm_only_after_team_is_built(self):
        task = self._load_task()
        task._verify_armed_team.return_value = True
        chars = []
        for index in range(4):
            char = Mock()
            char.index = index
            char.element = Element.WHITE
            char.char_name = f"char_{index}"
            char.confidence = 0.95
            char.combo_name = "builtin"
            chars.append(char)
        task._do_load_char.side_effect = chars

        manager = Mock()
        preset = self._preset()
        manager.get_fixed_team.return_value = {
            "enabled": True,
            "active_preset_id": "team_a",
            "slots": preset["slots"],
        }
        manager.get_armed_team_preset.return_value = preset
        manager.consume_armed_team_preset.return_value = preset

        with patch("src.combat.BaseCombatTask.CustomCharManager", return_value=manager):
            loaded = BaseCombatTask.load_chars(task)

        self.assertTrue(loaded)
        self.assertEqual(task.chars, chars)
        manager.consume_armed_team_preset.assert_called_once_with("team_a")
        self.assertEqual(task.active_team_preset_id, "team_a")
        task.combat_planner.reset.assert_called_once_with(chars)

    def test_auto_load_uses_visible_slot_order_and_keeps_all_presets_available(self):
        task = self._load_task()
        visible = self._visible_match(
            "team_lower",
            ("char_3", "char_1", "char_0", "char_2"),
        )
        chars = []
        for index in range(4):
            char = Mock()
            char.index = index
            char.element = Element.WHITE
            char.char_name = f"char_{index}"
            char.confidence = 0.95
            char.combo_name = "builtin"
            chars.append(char)
        task._do_load_char.side_effect = chars

        manager = Mock()
        manager.get_fixed_team.return_value = {
            "enabled": False,
            "selection_mode": "auto",
            "active_preset_id": "team_upper",
            "slots": [],
            "presets": {"team_upper": {}, "team_lower": {}},
        }
        manager.get_armed_team_preset.return_value = None

        with patch("src.combat.BaseCombatTask.CustomCharManager", return_value=manager):
            loaded = BaseCombatTask.load_chars(task, visible_match=visible)

        self.assertTrue(loaded)
        self.assertEqual(task.active_team_preset_id, "team_lower")
        self.assertEqual(task._team_binding, visible)
        self.assertEqual(
            [call.args[0] for call in task._do_load_char.call_args_list],
            list(range(4)),
        )
        self.assertEqual(
            [call.args[1] for call in task._do_load_char.call_args_list],
            [visible.slots] * 4,
        )
        manager.consume_armed_team_preset.assert_not_called()

    def test_auto_mode_keeps_generic_detection_for_a_new_unmatched_battle(self):
        task = self._load_task()
        chars = []
        for index in range(4):
            char = Mock()
            char.index = index
            char.element = Element.WHITE
            char.char_name = f"char_{index}"
            char.confidence = 0.95
            char.combo_name = "builtin"
            chars.append(char)
        task._do_load_char.side_effect = chars
        task._match_visible_team_preset = Mock(return_value=None)
        task._probe_visible_team = Mock(return_value=(None, 0))

        manager = Mock()
        manager.get_fixed_team.return_value = {
            "enabled": False,
            "selection_mode": "auto",
            "active_preset_id": "team_upper",
            "slots": [],
            "presets": {"team_upper": {}, "team_lower": {}},
        }
        manager.get_armed_team_preset.return_value = None

        with patch("src.combat.BaseCombatTask.CustomCharManager", return_value=manager):
            loaded = BaseCombatTask.load_chars(task)

        self.assertTrue(loaded)
        self.assertEqual(task.active_team_preset_id, "")
        self.assertFalse(hasattr(task, "_team_binding"))
        self.assertEqual(
            [call.args[1] for call in task._do_load_char.call_args_list],
            [[]] * 4,
        )

    def test_partial_known_abyss_holds_input_and_fails_closed(self):
        """Three known saved profiles + one low-confidence slot must not create generic chars."""
        task = self._load_task()
        task._match_visible_team_preset = Mock(return_value=None)
        task._probe_visible_team = Mock(return_value=(None, 2))
        task._stabilize_partial_recognition = Mock(return_value=None)
        task.sleep = Mock()

        manager = Mock()
        manager.get_fixed_team.return_value = {
            "enabled": False,
            "selection_mode": "auto",
            "active_preset_id": "",
            "slots": [],
            "presets": {"team_upper": {}, "team_lower": {}},
        }
        manager.get_armed_team_preset.return_value = None

        with patch("src.combat.BaseCombatTask.CustomCharManager", return_value=manager):
            loaded = BaseCombatTask.load_chars(task)

        self.assertFalse(loaded)
        task._do_load_char.assert_not_called()
        task.combat_planner.reset.assert_not_called()

    def test_partial_known_abyss_binds_on_stabilized_retry(self):
        """A following complete unique frame must bind the expected preset in HUD slot order."""
        task = self._load_task()
        visible = self._visible_match(
            "team_lower",
            ("char_3", "char_1", "char_0", "char_2"),
        )
        task._match_visible_team_preset = Mock(return_value=None)
        task._probe_visible_team = Mock(return_value=(None, 1))
        task._stabilize_partial_recognition = Mock(return_value=visible)
        task.sleep = Mock()

        chars = []
        for index in range(4):
            char = Mock()
            char.index = index
            char.element = Element.WHITE
            char.char_name = f"char_{index}"
            char.confidence = 0.95
            char.combo_name = "builtin"
            chars.append(char)
        task._do_load_char.side_effect = chars

        manager = Mock()
        manager.get_fixed_team.return_value = {
            "enabled": False,
            "selection_mode": "auto",
            "active_preset_id": "",
            "slots": [],
            "presets": {"team_upper": {}, "team_lower": {}},
        }
        manager.get_armed_team_preset.return_value = None

        with patch("src.combat.BaseCombatTask.CustomCharManager", return_value=manager):
            loaded = BaseCombatTask.load_chars(task)

        self.assertTrue(loaded)
        self.assertEqual(task.active_team_preset_id, "team_lower")
        self.assertEqual(task._team_binding, visible)
        self.assertEqual(
            [call.args[1] for call in task._do_load_char.call_args_list],
            [visible.slots] * 4,
        )
        task.combat_planner.reset.assert_called_once_with(chars)


if __name__ == "__main__":
    unittest.main()
