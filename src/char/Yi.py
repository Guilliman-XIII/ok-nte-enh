from src.char.BaseChar import BaseChar
from src.combat.planner import FieldPreference, Role, RoleProfile


class Yi(BaseChar):
    """翳的深渊盈蓄队最小入场逻辑：Q 后接 E，完成铺垫即离场。"""

    def describe_role(self):
        return RoleProfile(
            role=Role.SUB_DPS,
            field_preference=FieldPreference.SETUP_ONLY,
            max_field_time=0,
        )

    def combat_plan(self, context):
        return self.plan(
            self.click_ultimate_action(),
            self.click_skill_action(),
        )
