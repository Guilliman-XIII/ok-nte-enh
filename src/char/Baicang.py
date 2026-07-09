import time

from src.char.BaseChar import BaseChar
from src.combat.planner import (
    ActionSlot,
    ActionTag,
    CombatContext,
    FieldClaim,
    FieldPreference,
    Role,
    RoleProfile,
)

_LOG_PREFIX = "[Baicang]"


class Baicang(BaseChar):
    """白藏 - 咒系(RED)主C，以闪避(右键)攻击为核心输出。

    结构参考 Nanally: E/Q 分离为 planner-visible action，
    Q 成功后进入角色专属爆发循环，循环内第二 E 检查 SKILL reservation。
    """

    MAX_FIELD_TIME = 2.0
    ULT_FIELD_DURATION = 8.0
    FALLBACK_DODGE_DURATION = 1.5
    DODGE_CLICK_INTERVAL = 0.12
    DODGE_SLICE_DURATION = 0.3
    SKILL_CHECK_INTERVAL = 1.5
    SECOND_SKILL_MODE = "observe"  # disabled | observe | execute
    SKILL_READY_STREAK_THRESHOLD = 3
    SKILL_SHORT_TIMEOUT = 2.0
    DEFAULT_DIRECTION_KEY = "w"

    def describe_role(self):
        return RoleProfile(
            role=Role.MAIN_DPS,
            field_preference=FieldPreference.MAIN_DPS,
            max_field_time=self.MAX_FIELD_TIME,
        )

    def combat_plan(self, context: CombatContext):
        skill = self.click_skill_action(reason="baicang skill")
        ultimate = self.click_ultimate_action(reason="baicang ultimate")
        fallback_dodge = self.planner_action(
            tags={ActionTag.DEFAULT_ACTION, ActionTag.DAMAGE},
            execute=lambda ctx: self._execute_fallback_dodge(),
            name="baicang_dodge_fallback",
            reason="baicang fallback dodge",
            priority_ready=lambda ctx: False,
        )

        claims = []
        if self.ultimate_available():
            claims.append(
                FieldClaim.high(
                    reason="baicang burst window (ultimate ready)",
                )
            )

        def entry():
            skill_result = yield skill
            if skill_result and self.ultimate_available():
                self.sleep(0.3)

            ultimate_result = yield ultimate
            if ultimate_result:
                self._perform_burst(context)
                return

            if not skill_result:
                yield fallback_dodge

        return self.plan(skill, ultimate, fallback_dodge, claims=claims, entry=entry)

    def _perform_burst(self, context: CombatContext = None):
        """Q 成功后的爆发输出循环 (参考 Nanally.perform_in_ult)。

        - 方向键在整个循环期间持续按住
        - 循环受 ``ULT_FIELD_DURATION`` 限时
        - 每个分片后检查: deadline、is_current_char、is_dead、check_combat
        - 第二 E 保护链 (参考 Nanally._try_skill_during_ultimate)
        """
        self.logger.info(f"{_LOG_PREFIX} burst start")
        start = self._now()
        deadline = start + self.ULT_FIELD_DURATION
        direction_key = self.DEFAULT_DIRECTION_KEY

        track_second_skill = self.SECOND_SKILL_MODE != "disabled"
        cooldown_confirmed = False
        ready_streak = 0
        second_skill_done = False
        last_check = start

        try:
            self.task.send_key_down(direction_key)
            self.sleep(0.1)

            while self._now() < deadline:
                if not self.is_current_char:
                    self.logger.info(f"{_LOG_PREFIX} burst end (not current char)")
                    return
                if self.is_dead:
                    self.logger.info(f"{_LOG_PREFIX} burst end (dead)")
                    return

                remaining = deadline - self._now()
                slice_dur = min(self.DODGE_SLICE_DURATION, remaining)
                if slice_dur > 0:
                    self._right_click_burst(slice_dur)

                self.check_combat()

                if not track_second_skill or second_skill_done:
                    self.sleep(0.1)
                    continue
                if self._now() - last_check < self.SKILL_CHECK_INTERVAL:
                    self.sleep(0.1)
                    continue

                last_check = self._now()
                skill_ready = self.skill_available()

                if not cooldown_confirmed:
                    if not skill_ready:
                        cooldown_confirmed = True
                        self.logger.info(f"{_LOG_PREFIX} skill cooldown confirmed")
                    self.sleep(0.1)
                    continue

                if skill_ready:
                    ready_streak += 1
                    if ready_streak == 1 or ready_streak == self.SKILL_READY_STREAK_THRESHOLD:
                        self.logger.info(
                            f"{_LOG_PREFIX} second skill streak="
                            f"{ready_streak}/{self.SKILL_READY_STREAK_THRESHOLD}"
                        )
                else:
                    if ready_streak > 0:
                        self.logger.info(f"{_LOG_PREFIX} streak reset (was {ready_streak})")
                    ready_streak = 0
                    self.sleep(0.1)
                    continue

                if ready_streak < self.SKILL_READY_STREAK_THRESHOLD:
                    self.sleep(0.1)
                    continue

                if self.SECOND_SKILL_MODE == "execute":
                    self._try_second_skill(context)
                else:
                    self.logger.info(f"{_LOG_PREFIX} second skill armed (observe mode)")
                second_skill_done = True
                self.sleep(0.1)
        finally:
            self.task.send_key_up(direction_key)

        self.logger.info(f"{_LOG_PREFIX} burst end")

    def _try_second_skill(self, context: CombatContext = None):
        """参考 Nanally._try_skill_during_ultimate: 检查 reservation 后发送第二 E。"""
        if context is not None and not context.can_execute_action(self, slot=ActionSlot.SKILL):
            self.logger.info(f"{_LOG_PREFIX} second skill blocked by reservation")
            return False

        self.logger.info(f"{_LOG_PREFIX} second skill armed")
        clicked = self.click_skill(time_out=self.SKILL_SHORT_TIMEOUT)
        if clicked:
            self.logger.info(f"{_LOG_PREFIX} second skill executed")
        else:
            self.logger.info(f"{_LOG_PREFIX} second skill click failed")
        return clicked

    def _execute_fallback_dodge(self):
        """Q/E 均不可用时的兜底：有限时长的闪避攻击。"""
        if self.is_dead or not self.is_current_char:
            self.logger.info(f"{_LOG_PREFIX} fallback dodge skipped (dead or not current)")
            return False

        self.logger.info(f"{_LOG_PREFIX} fallback dodge")
        self.continues_right_click(
            self.FALLBACK_DODGE_DURATION,
            interval=self.DODGE_CLICK_INTERVAL,
            direction_key=self.DEFAULT_DIRECTION_KEY,
        )

        if not self.is_current_char or self.is_dead:
            self.logger.info(f"{_LOG_PREFIX} fallback dodge ended (char changed or dead)")
            return False

        return True

    def _right_click_burst(self, duration):
        """持续右键点击 ``duration`` 秒，不管理方向键。"""
        if duration <= 0:
            return
        interval = self.DODGE_CLICK_INTERVAL
        start = self._now()
        while self._now() - start < duration:
            self.click(interval=interval, key="right")

    def _now(self):
        """可 patch 的时钟，供测试覆盖。"""
        return time.monotonic()

    def on_combat_end(self, chars):
        """战斗结束后尝试切人，释放主 C 站场。"""
        self.switch_other_char()
