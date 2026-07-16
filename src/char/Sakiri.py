from src.char.BaseChar import BaseChar
from src.combat.planner import (
    ActionSlot,
    CombatContext,
    FieldPreference,
    Role,
    RoleProfile,
)


class Sakiri(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def describe_role(self):
        from src.char.Baicang import Baicang

        is_baicang_abyss_team = Baicang.is_abyss_team(self.task.chars)
        return RoleProfile(
            role=Role.SUB_DPS,
            field_preference=(
                FieldPreference.SETUP_ONLY if is_baicang_abyss_team else FieldPreference.SUB_DPS
            ),
            combat_start_priority=100 if is_baicang_abyss_team else 0,
            max_field_time=0 if is_baicang_abyss_team else 1.0,
        )

    def combat_plan(self, context):
        from src.char.Baicang import Baicang

        is_baicang_abyss_team = Baicang.is_abyss_team(self.task.chars)
        ultimate = self.click_ultimate_action(
            can_execute=lambda _: not is_baicang_abyss_team,
        )
        skill = self.click_skill_action(
            down_time=0.25,
            can_execute=lambda ctx: (
                not is_baicang_abyss_team
                or ctx.strict_route_wants_action(self, slot=ActionSlot.SKILL)
            ),
        )

        def entry():
            yield ultimate
            yield skill
            self._request_baicang_return(context)

        return self.plan(ultimate, skill, entry=entry)

    def _request_baicang_return(self, context: CombatContext = None) -> None:
        from src.char.Baicang import Baicang

        Baicang.request_abyss_return(
            context,
            self.task.chars,
            reason="return Baicang after Sakiri setup",
        )
