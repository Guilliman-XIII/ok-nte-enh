import re
import time

from src.char.BaseChar import BaseChar
from src.combat.planner import (
    ActionSlot,
    CombatContext,
    FieldPreference,
    FollowupStep,
    Role,
    RoleProfile,
)


class Chiz(BaseChar):
    ABYSS_OPENER_TIMEOUT = 35.0
    ULT_FIELD_DURATION = 8.0
    SKILL_SHORT_TIMEOUT = 2.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def is_abyss_team(chars):
        """仅识别小吱、九原、翳、零的固定盈蓄队。"""
        from src.char.Jiuyuan import Jiuyuan
        from src.char.Yi import Yi
        from src.char.Zero import Zero

        required = (Chiz, Jiuyuan, Yi, Zero)
        return len(chars) == 4 and all(
            sum(isinstance(char, char_cls) for char in chars) == 1 for char_cls in required
        )

    def combat_policies(self, context: CombatContext) -> None:
        if not self.is_abyss_team(self.task.chars):
            return

        from src.char.Jiuyuan import Jiuyuan
        from src.char.Yi import Yi
        from src.char.Zero import Zero

        jiuyuan = next(char for char in self.task.chars if isinstance(char, Jiuyuan))
        yi = next(char for char in self.task.chars if isinstance(char, Yi))
        zero = next(char for char in self.task.chars if isinstance(char, Zero))
        route_started_at = None

        def route_expired():
            nonlocal route_started_at
            now = time.monotonic()
            if route_started_at is None:
                route_started_at = now
                return False
            return now - route_started_at >= self.ABYSS_OPENER_TIMEOUT

        context.request_route(
            [
                FollowupStep.for_action(
                    jiuyuan,
                    ActionSlot.SKILL,
                    reason="Jiuyuan groups enemies for Yingxu opener",
                ),
                FollowupStep.for_action(
                    zero,
                    ActionSlot.ULTIMATE,
                    reason="Zero adds light setup",
                    optional=True,
                ),
                FollowupStep.for_action(
                    zero,
                    ActionSlot.SKILL,
                    reason="Zero fills the first element ring",
                ),
                FollowupStep.for_entry_reaction(
                    jiuyuan,
                    reason="Jiuyuan triggers Creation from the first ring",
                ),
                FollowupStep.for_action(
                    jiuyuan,
                    ActionSlot.ULTIMATE,
                    reason="Jiuyuan adds off-field spirit damage",
                    optional=True,
                ),
                FollowupStep.for_action(
                    jiuyuan,
                    ActionSlot.SKILL,
                    reason="Jiuyuan refreshes grouping if ready",
                    optional=True,
                ),
                FollowupStep.for_action(
                    zero,
                    ActionSlot.SKILL,
                    reason="Zero fills the second element ring",
                ),
                FollowupStep.for_entry_reaction(
                    yi,
                    reason="Yi triggers Delay from the second ring",
                ),
                FollowupStep.for_action(
                    yi,
                    ActionSlot.ULTIMATE,
                    reason="Yi applies ultimate setup",
                    optional=True,
                ),
                FollowupStep.for_action(
                    yi,
                    ActionSlot.SKILL,
                    reason="Yi applies aspect setup",
                ),
                FollowupStep.for_action(
                    self,
                    ActionSlot.ULTIMATE,
                    reason="Chiz spends Yingxu energy in the damage window",
                ),
            ],
            reason="Chiz Yingxu abyss opener",
            until=route_expired,
        )

    def describe_role(self):
        return RoleProfile(
            role=Role.MAIN_DPS,
            field_preference=FieldPreference.MAIN_DPS,
        )

    def combat_plan(self, context):
        ultimate = self.click_ultimate_action()
        skill = self.click_skill_action()

        def entry():
            ultimate_result = yield ultimate
            if ultimate_result:
                self.perform_in_ult(context)
                return
            yield skill

        return self.plan(ultimate, skill, entry=entry)

    def perform_in_ult(self, context: CombatContext = None):
        box = self.task.box_of_screen(0.487, 0.775, 0.514, 0.798, name="percentage")
        self.task.wait_ocr(
            box=box,
            match=re.compile(r"-?\d+%", re.IGNORECASE),
            time_out=2,
            raise_if_not_found=False,
        )
        deadline = self._now() + self.ULT_FIELD_DURATION
        skill_attempted = False
        while self._now() < deadline:
            if not self.is_current_char or self.is_dead:
                return
            self.check_combat()
            red_pct = self.task.calculate_color_percentage(red_pct_color, box)
            yellow_pct = self.task.calculate_color_percentage(yellow_pct_color, box)
            if (
                not skill_attempted
                and yellow_pct > red_pct
                and self.skill_available()
                and (context is None or context.can_execute_action(self, slot=ActionSlot.SKILL))
            ):
                skill_attempted = True
                self.click_skill(time_out=self.SKILL_SHORT_TIMEOUT)
            self.click_with_interval()
            self.sleep(0.1)

    def _now(self):
        return time.monotonic()


red_pct_color = {
    "r": (250, 255),
    "g": (115, 125),
    "b": (115, 120),
}

yellow_pct_color = {
    "r": (250, 255),
    "g": (230, 240),
    "b": (120, 125),
}
