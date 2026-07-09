from src.char.BaseChar import BaseChar
from src.combat.planner import (
    CombatContext,
    FieldPreference,
    Role,
    RoleProfile,
)

_LOG_PREFIX = "[Hania]"


class Hania(BaseChar):
    """哈妮娅 - 魂系(BLUE)辅助。

    SUB_DPS, SETUP_ONLY: Q 强化领域 → E 部署咕咕子 → 切出。
    详细游戏机制见 docs/research/hania.md。
    """

    MAX_FIELD_TIME = 3.0

    def describe_role(self):
        return RoleProfile(
            role=Role.SUB_DPS,
            field_preference=FieldPreference.SETUP_ONLY,
            max_field_time=self.MAX_FIELD_TIME,
        )

    def combat_plan(self, context: CombatContext):
        ultimate = self.click_ultimate_action(reason="hania ultimate (enhanced domain)")
        skill = self.click_skill_action(reason="hania skill (deploy 咕咕子)")

        def entry():
            ultimate_result = yield ultimate
            if ultimate_result:
                self.logger.info(f"{_LOG_PREFIX} enhanced domain active")
                self.sleep(0.3)
            skill_result = yield skill
            if skill_result:
                self.logger.info(f"{_LOG_PREFIX} 咕咕子 deployed")
                self.sleep(0.5)

        return self.plan(ultimate, skill, entry=entry)

    def on_combat_end(self, chars):
        """战斗结束后切出，让主C站场。"""
        self.switch_other_char()
