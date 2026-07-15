
from src.char.BaseChar import BaseChar
from src.combat.planner import FieldPreference, Role, RoleProfile


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
        return self.plan(
            self.click_ultimate_action(),
            self.click_skill_action(down_time=0.25),
        )
