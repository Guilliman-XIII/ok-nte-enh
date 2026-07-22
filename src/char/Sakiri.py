from src.char.BaseChar import BaseChar
from src.combat.planner import Planner, RoleProfile
from src.combat.skill_cooldown import SkillCooldownModel


class Sakiri(BaseChar):
    SKILL_HOLD_DURATION = 0.8
    SKILL_SETTLE_DURATION = 1.2
    GATHER_REUSE_INTERVAL = 10.0  # minimum seconds between re-gather attempts

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cooldowns = SkillCooldownModel(now_fn=lambda: self._now())

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

    def _gather_reuse_ready(self) -> bool:
        """True when enough time has passed to allow a re-gather outside the opener route."""
        return self._cooldowns.is_ready("gather")

    def combat_plan(self, context):
        from src.combat.team_strategies import is_baicang_abyss_team

        is_opener = is_baicang_abyss_team(self.task.chars)

        def _execute_gather(_):
            result = self.click_skill(
                down_time=self.SKILL_HOLD_DURATION,
                post_sleep=self.SKILL_SETTLE_DURATION,
            )
            if result:
                self._cooldowns.mark_used("gather", self.GATHER_REUSE_INTERVAL)
            return result

        skill = self.planner_action(
            tags={Planner.ActionTag.SKILL_ACTION},
            slot=Planner.ActionSlot.SKILL,
            execute=_execute_gather,
            name=f"{self}_skill",
            reason="Sakiri hold skill for grouping",
            can_execute=lambda ctx: (
                not is_opener
                or ctx.strict_route_wants_action(
                    self,
                    slot=Planner.ActionSlot.SKILL,
                )
                or (self.skill_available() and self._gather_reuse_ready())
            ),
            priority_ready=lambda _: self.skill_available() and self._gather_reuse_ready(),
        )
        return self.plan(
            self.click_ultimate_action(
                can_execute=lambda ctx: (
                    not is_opener
                    or ctx.strict_route_wants_action(
                        self,
                        slot=Planner.ActionSlot.ULTIMATE,
                    )
                ),
            ),
            skill,
        )

    def _now(self):
        import time

        return time.monotonic()
