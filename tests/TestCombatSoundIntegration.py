"""战斗长动作与声音闪避/反击的公共抢占边界测试。"""

import unittest
from unittest.mock import MagicMock, patch

from src.combat.BaseCombatTask import BaseCombatTask, SleepCheckSkip


class TestCombatSoundIntegration(unittest.TestCase):
    def _task(self):
        task = BaseCombatTask.__new__(BaseCombatTask)
        task.sleep_check_skip = SleepCheckSkip()
        task.in_animation = False
        task.log_info = MagicMock()
        task.check_combat = MagicMock()
        return task

    def test_sleep_checkpoint_executes_pending_sound_action(self):
        task = self._task()

        with patch("src.combat.BaseCombatTask.SoundCombatContext") as sound_context:
            sound_context.should_interrupt_combat.return_value = True

            task.sleep_check()

        sound_context.return_value.execute_pending_action.assert_called_once_with()
        sound_context.wait_for_resume.assert_called_once_with()
        task.check_combat.assert_called_once_with()

    def test_animation_defers_sound_action(self):
        task = self._task()
        task.in_animation = True

        with patch("src.combat.BaseCombatTask.SoundCombatContext") as sound_context:
            sound_context.should_interrupt_combat.return_value = True

            task.sleep_check()

        sound_context.return_value.execute_pending_action.assert_not_called()
        sound_context.wait_for_resume.assert_not_called()
        task.check_combat.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
