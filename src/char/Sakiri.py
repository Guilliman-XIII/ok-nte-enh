
from src.char.BaseChar import BaseChar
from src.combat.planner import CombatContext, FieldPreference, Role, RoleProfile


class Sakiri(BaseChar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def describe_role(self):
        from src.char.Baicang import Baicang

        return RoleProfile(
            role=Role.SUB_DPS,
            field_preference=FieldPreference.SUB_DPS,
            combat_start_priority=100 if Baicang.is_abyss_team(self.task.chars) else 0,
            max_field_time=1.0,
        )

    def combat_plan(self, context):
        ultimate = self.click_ultimate_action()
        skill = self.click_skill_action(down_time=0.25)

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
