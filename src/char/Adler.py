import time

from src.char.BaseChar import BaseChar
from src.combat.planner import (
    CombatContext,
    FieldPreference,
    Role,
    RoleProfile,
)

_LOG_PREFIX = "[Adler]"


class Adler(BaseChar):
    """阿德勒 - 咒系(RED)生存辅助。

    SUB_DPS, SETUP_ONLY: 入场叠业 → E 开盾 → Q → 切出。
    详细游戏机制见 docs/research/adler.md。
    """

    MAX_FIELD_TIME = 4.0
    YE_STACK_DURATION = 1.5
    YE_ATTACK_INTERVAL = 0.2

    def describe_role(self):
        return RoleProfile(
            role=Role.SUB_DPS,
            field_preference=FieldPreference.SETUP_ONLY,
            max_field_time=self.MAX_FIELD_TIME,
        )

    def combat_plan(self, context: CombatContext):
        skill = self.click_skill_action(reason="adler skill (consume 业 + shield)")
        ultimate = self.click_ultimate_action(reason="adler ultimate (AoE burst)")

        def entry():
            self._stack_ye()
            skill_result = yield skill
            if skill_result:
                self.logger.info(f"{_LOG_PREFIX} shield deployed")
                self.sleep(0.5)
            yield ultimate

        return self.plan(skill, ultimate, entry=entry)

    def _stack_ye(self):
        """入场快速普攻积累"业"层数。

        [EXTERNAL] 蓄力瞄准射击+2层/次，普攻+1层/次。
        此处使用普攻快速叠层，实机校准后可改为蓄力。
        """
        self.logger.info(f"{_LOG_PREFIX} stacking 业")
        start = self._now()
        while self._now() - start < self.YE_STACK_DURATION:
            if not self.is_current_char:
                return
            if self.is_dead:
                return
            self.check_combat()
            self.normal_attack()
            self.sleep(self.YE_ATTACK_INTERVAL)

    def _now(self):
        """可 patch 的时钟，供测试覆盖。"""
        return time.monotonic()

    def on_combat_end(self, chars):
        """战斗结束后切出，让主C站场。"""
        self.switch_other_char()
