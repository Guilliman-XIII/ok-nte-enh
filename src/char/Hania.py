from src.char.BaseChar import BaseChar
from src.combat.planner import (
    ActionSlot,
    ActionTag,
    CombatContext,
    FieldPreference,
    Role,
    RoleProfile,
)

_LOG_PREFIX = "[Hania]"
SKILL_SHORT_TIMEOUT = 2.0


class Hania(BaseChar):
    """哈妮娅 - 魂系(BLUE)辅助。

    SUB_DPS, SETUP_ONLY: Q 强化领域 → E 部署咕咕子 → 切出。
    保持简单结构，队伍协调由上层配置决定。
    详细游戏机制见 docs/research/hania.md。
    """

    MAX_FIELD_TIME = 0  # 禁止通用平A fallback

    def describe_role(self):
        return RoleProfile(
            role=Role.SUB_DPS,
            field_preference=FieldPreference.SETUP_ONLY,
            max_field_time=self.MAX_FIELD_TIME,
        )

    def combat_plan(self, context: CombatContext):
        ultimate = self.click_ultimate_action(reason="hania ultimate (enhanced domain)")
        skill = self.planner_action(
            tags={ActionTag.SKILL_ACTION},
            slot=ActionSlot.SKILL,
            execute=lambda ctx: self.click_skill(time_out=SKILL_SHORT_TIMEOUT),
            name="hania_skill",
            reason="hania skill (deploy 咕咕子)",
            priority_ready=lambda _: self.skill_available(),
        )

        def entry():
            ultimate_result = yield ultimate
            if ultimate_result:
                self.logger.info(f"{_LOG_PREFIX} enhanced domain active")
                self.sleep(0.3)
            skill_result = yield skill
            if skill_result:
                self.logger.info(f"{_LOG_PREFIX} 咕咕子 deployed")
                self.sleep(0.5)
            self._request_baicang_return(context)

        return self.plan(ultimate, skill, entry=entry)

    def _request_baicang_return(self, context: CombatContext = None) -> None:
        from src.char.Baicang import Baicang

        Baicang.request_abyss_return(
            context,
            self.task.chars,
            reason="return Baicang after Hania setup",
        )

    def on_combat_end(self, chars):
        """战后清理。不用于战斗内切人。"""
        pass
