import unittest
from unittest.mock import Mock, PropertyMock, patch

import numpy as np

from src.char.BaseChar import Element
from src.combat.BaseCombatTask import BaseCombatTask


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


if __name__ == "__main__":
    unittest.main()
