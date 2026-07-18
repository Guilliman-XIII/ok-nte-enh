from src.char.BaseChar import BaseChar
from src.combat.planner import Planner, RoleProfile


class Sakiri(BaseChar):
    SKILL_HOLD_DURATION = 0.8
    SKILL_SETTLE_DURATION = 1.2

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def describe_role(self):
        from src.combat.team_strategies import is_baicang_abyss_team

        is_opener = is_baicang_abyss_team(self.task.chars)
        return RoleProfile(
            role=Planner.Role.SUB_DPS,
            field_preference=(
                Planner.FieldPreference.SETUP_ONLY
                if is_opener
                else Planner.FieldPreference.SUB_DPS
            ),
            combat_start_priority=100 if is_opener else 0,
            max_field_time=0 if is_opener else 1.0,
        )

    def combat_plan(self, context):
        from src.combat.team_strategies import is_baicang_abyss_team

        is_opener = is_baicang_abyss_team(self.task.chars)
        skill = self.planner_action(
            tags={Planner.ActionTag.SKILL_ACTION},
            slot=Planner.ActionSlot.SKILL,
            execute=lambda _: self.click_skill(
                down_time=self.SKILL_HOLD_DURATION,
                post_sleep=self.SKILL_SETTLE_DURATION,
            ),
            name=f"{self}_skill",
            reason="Sakiri hold skill for grouping",
            can_execute=lambda ctx: (
                not is_opener
                or ctx.strict_route_wants_action(
                    self,
                    slot=Planner.ActionSlot.SKILL,
                )
            ),
            priority_ready=lambda _: self.skill_available(),
        )
        return self.plan(
            self.click_ultimate_action(
                can_execute=lambda _: not is_opener,
            ),
            skill,
        )
