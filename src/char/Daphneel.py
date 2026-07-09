import time

from src.char.BaseChar import BaseChar
from src.combat.planner import (
    CombatContext,
    FieldPreference,
    Role,
    RoleProfile,
)

_LOG_PREFIX = "[Daphneel]"


class Daphneel(BaseChar):
    """达芙蒂尔 - 暗系(PURPLE)主C。

    Q 优先 (弹反充能后) → E (同振补充)，Q 后进入爆发窗口。
    弹反为操作依赖，无法自动检测。详细机制见 docs/research/daphneel.md。
    """

    MAX_FIELD_TIME = 10.0
    ULT_BURST_DURATION = 6.0
    BURST_ATTACK_INTERVAL = 0.2
    SKILL_SHORT_TIMEOUT = 2.0

    def describe_role(self):
        return RoleProfile(
            role=Role.MAIN_DPS,
            field_preference=FieldPreference.MAIN_DPS,
            max_field_time=self.MAX_FIELD_TIME,
        )

    def combat_plan(self, context: CombatContext):
        ultimate = self.click_ultimate_action(reason="daphneel ultimate (burst)")
        skill = self.click_skill_action(reason="daphneel skill (同振)")

        def entry():
            ultimate_result = yield ultimate
            if ultimate_result:
                self.logger.info(f"{_LOG_PREFIX} burst executed")
                self._perform_burst(context)
                return
            yield skill

        return self.plan(ultimate, skill, entry=entry)

    def _perform_burst(self, context: CombatContext = None):
        """Q 成功后的爆发输出窗口 (参考 Chiz.perform_in_ult)。

        - 持续普攻输出，检测 E 是否可用
        - E 可用时检查 reservation 后释放 (参考 Nanally._try_skill_during_ultimate)
        - 循环受 ``ULT_BURST_DURATION`` 限时
        """
        self.logger.info(f"{_LOG_PREFIX} burst start")
        start = self._now()
        deadline = start + self.ULT_BURST_DURATION
        skill_used = False

        while self._now() < deadline:
            if not self.is_current_char:
                self.logger.info(f"{_LOG_PREFIX} burst end (not current char)")
                return
            if self.is_dead:
                self.logger.info(f"{_LOG_PREFIX} burst end (dead)")
                return

            self.check_combat()

            if not skill_used and self.skill_available():
                skill_used = self._try_skill_during_burst(context)

            self.normal_attack()
            self.sleep(self.BURST_ATTACK_INTERVAL)

        self.logger.info(f"{_LOG_PREFIX} burst end")

    def _try_skill_during_burst(self, context: CombatContext = None):
        """参考 Nanally._try_skill_during_ultimate: 检查 reservation 后释放 E。"""
        from src.combat.planner import ActionSlot

        if context is not None and not context.can_execute_action(self, slot=ActionSlot.SKILL):
            self.logger.debug(f"{_LOG_PREFIX} skill blocked by reservation")
            return False

        self.logger.info(f"{_LOG_PREFIX} second skill during burst")
        return self.click_skill(time_out=self.SKILL_SHORT_TIMEOUT)

    def _now(self):
        """可 patch 的时钟，供测试覆盖。"""
        return time.monotonic()

    def on_combat_end(self, chars):
        """战斗结束后切人。"""
        self.switch_other_char()
