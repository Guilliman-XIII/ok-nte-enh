import re
import time

from src.char.BaseChar import BaseChar
from src.combat.planner import CombatContext, Planner, RoleProfile


class Chiz(BaseChar):
    ABYSS_ROUTE_TIMEOUT = 35.0
    ULT_FIELD_DURATION = 8.0
    SKILL_SHORT_TIMEOUT = 2.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def is_abyss_team(chars):
        from src.combat.team_strategies import is_chiz_abyss_team

        return is_chiz_abyss_team(chars)

    def _request_yingxu_route(self, context: CombatContext, opener: bool) -> None:
        from src.combat.team_strategies import request_chiz_route

        request_chiz_route(context, opener=opener)

    def describe_role(self):
        return RoleProfile(
            role=Planner.Role.MAIN_DPS,
            field_preference=Planner.FieldPreference.MAIN_DPS,
        )

    def combat_plan(self, context):
        ultimate = self.click_ultimate_action()
        skill = self.click_skill_action()

        def entry():
            ultimate_result = yield ultimate
            if ultimate_result:
                if self.perform_in_ult(context):
                    self._request_yingxu_route(context, opener=False)
                return
            yield skill

        return self.plan(ultimate, skill, entry=entry)

    def perform_in_ult(self, context: CombatContext = None) -> bool:
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
                return False
            self.check_combat()
            red_pct = self.task.calculate_color_percentage(red_pct_color, box)
            yellow_pct = self.task.calculate_color_percentage(yellow_pct_color, box)
            if (
                not skill_attempted
                and yellow_pct > red_pct
                and self.skill_available()
                and (
                    context is None
                    or context.can_execute_action(self, slot=Planner.ActionSlot.SKILL)
                )
            ):
                skill_attempted = True
                self.click_skill(time_out=self.SKILL_SHORT_TIMEOUT)
            self.click_with_interval()
            self.sleep(0.1)
        return self.is_current_char and not self.is_dead

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
