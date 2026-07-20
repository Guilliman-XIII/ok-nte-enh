import time

from src.char.BaseChar import BaseChar
from src.combat.planner import (
    ActionSlot,
    ActionTag,
    CombatContext,
    FieldPreference,
    Role,
    RoleProfile,
)

_LOG_PREFIX = "[Baicang]"


class Baicang(BaseChar):
    """Baicang main DPS with bounded normal-attack baseline and optional Shift-AOE.

    The default output is conservative bounded left-click normal attacks with E/Q
    gating. Sound-triggered dodge and counter logic remains owned by BaseCombatTask.

    Shift-AOE spin (player technique, currently DISABLED):
      The player holds Shift continuously AND holds a direction key (A) to
      spin in place, sweeping AOE around grouped enemies. This relies on
      real-time visual adjustment the script cannot do, so it is disabled by
      default. Re-enable BURST_DIRECTION_KEY / BURST_HOLD_SHIFT once the
      exact input pattern is taught and verified against a recording.
    """

    MAX_FIELD_TIME = 0
    ULT_FIELD_DURATION = 12.0
    FALLBACK_DODGE_DURATION = 1.5
    NORMAL_ATTACK_INTERVAL = 0.18
    ATTACK_SLICE_DURATION = 0.36
    DODGE_CLICK_INTERVAL = 0.12
    DODGE_SLICE_DURATION = 0.12
    SKILL_CHECK_INTERVAL = 0.8
    SECOND_SKILL_MODE = "execute"  # disabled | observe | execute
    SKILL_READY_STREAK_THRESHOLD = 2
    SKILL_SHORT_TIMEOUT = 2.0
    DEFAULT_DIRECTION_KEY = None
    BURST_DIRECTION_KEY = None  # e.g. "a" to spin; disabled until technique is taught
    BURST_HOLD_SHIFT = False  # hold Shift during burst; disabled until technique is taught
    ARC_CHECK_INTERVAL = 2.0  # seconds between R attempts during burst
    POST_SKILL_DODGE_DURATION = 1.0
    ABYSS_OPENER_TIMEOUT = 24.0

    @staticmethod
    def is_abyss_team(chars):
        from src.combat.team_strategies import is_baicang_abyss_team

        return is_baicang_abyss_team(chars)

    @classmethod
    def request_abyss_return(cls, context: CombatContext, chars, reason: str) -> None:
        """目标队辅助完成动作后显式请求白藏回场，即使白藏 E/Q 正在冷却。"""
        if context is None or not cls.is_abyss_team(chars):
            return
        baicang = next(char for char in chars if isinstance(char, cls))
        context.request_switch(baicang, reason=reason)

    def combat_policies(self, context: CombatContext) -> None:
        return None

    def describe_role(self):
        return RoleProfile(
            role=Role.MAIN_DPS,
            field_preference=FieldPreference.MAIN_DPS,
            max_field_time=self.MAX_FIELD_TIME,
        )

    def combat_plan(self, context: CombatContext):
        skill = self.planner_action(
            tags={ActionTag.SKILL_ACTION},
            slot=ActionSlot.SKILL,
            execute=lambda ctx: self.click_skill(time_out=self.SKILL_SHORT_TIMEOUT),
            name="baicang_skill",
            reason="baicang skill",
            can_execute=lambda _: self.skill_available(),
            priority_ready=lambda _: self.skill_available(),
        )
        ultimate = self.click_ultimate_action(
            reason="baicang ultimate",
            can_execute=lambda _: self.ultimate_available(),
        )
        fallback_dodge = self.planner_action(
            tags={ActionTag.DEFAULT_ACTION, ActionTag.DAMAGE},
            execute=lambda ctx: self._execute_fallback_dodge(),
            name="baicang_dodge_fallback",
            reason="baicang fallback dodge",
            priority_ready=lambda ctx: False,
        )

        def entry():
            ultimate_result = yield ultimate
            if ultimate_result:
                self._perform_burst(context)
                return

            skill_result = yield skill
            if skill_result:
                self._post_skill_dodge()
            else:
                yield fallback_dodge

        return self.plan(skill, ultimate, fallback_dodge, entry=entry)

    def _perform_burst(self, context: CombatContext = None):
        """Q 成功后的爆发输出循环 (参考 Nanally.perform_in_ult)。

        - BURST_DIRECTION_KEY (A) + Shift 全程按住: A 使白藏原地转身,
          Shift 冲刺攻击扫成一圈 AOE
        - 循环受 ``ULT_FIELD_DURATION`` 限时
        - 每个分片后检查: deadline、is_current_char、is_dead、check_combat
        - E 冷却好后自动释放 (SECOND_SKILL_MODE=execute)
        """
        self.logger.info(f"{_LOG_PREFIX} burst start")
        start = self._now()
        deadline = start + self.ULT_FIELD_DURATION
        direction_key = self.BURST_DIRECTION_KEY or self.DEFAULT_DIRECTION_KEY
        hold_shift = self.BURST_HOLD_SHIFT

        track_second_skill = self.SECOND_SKILL_MODE != "disabled"
        ready_streak = 0
        last_check = start
        last_arc = start

        try:
            if direction_key is not None:
                self.task.send_key_down(direction_key)
            if hold_shift:
                self.task.send_key_down("lshift")
            if direction_key is not None or hold_shift:
                self.sleep(0.1)

            while self._now() < deadline:
                if not self.is_current_char:
                    self.logger.info(f"{_LOG_PREFIX} burst end (not current char)")
                    return
                if self.is_dead:
                    self.logger.info(f"{_LOG_PREFIX} burst end (dead)")
                    return

                remaining = deadline - self._now()
                slice_dur = min(self.ATTACK_SLICE_DURATION, remaining)
                if slice_dur > 0:
                    self._normal_attack_slice(slice_dur)

                if self._now() - last_arc >= self.ARC_CHECK_INTERVAL:
                    last_arc = self._now()
                    self.send_arc_key(action_name=("baicang_burst_arc", self.index))

                self.sleep(0.01)
                self.check_combat()

                if not track_second_skill:
                    self.sleep(0.1)
                    continue
                if self._now() - last_check < self.SKILL_CHECK_INTERVAL:
                    self.sleep(0.1)
                    continue

                last_check = self._now()
                if self.skill_available():
                    ready_streak += 1
                    if ready_streak == 1:
                        self.logger.info(
                            f"{_LOG_PREFIX} skill ready streak="
                            f"{ready_streak}/{self.SKILL_READY_STREAK_THRESHOLD}"
                        )
                else:
                    if ready_streak > 0:
                        self.logger.debug(f"{_LOG_PREFIX} skill streak reset (was {ready_streak})")
                    ready_streak = 0
                    self.sleep(0.1)
                    continue

                if ready_streak < self.SKILL_READY_STREAK_THRESHOLD:
                    self.sleep(0.1)
                    continue

                if self.SECOND_SKILL_MODE == "execute":
                    if self._try_second_skill(context):
                        ready_streak = 0  # allow E to fire again after next cooldown
                else:
                    self.logger.info(f"{_LOG_PREFIX} skill armed (observe mode)")
                    ready_streak = 0
                self.sleep(0.1)
        finally:
            if direction_key is not None:
                self.task.send_key_up(direction_key)
            if hold_shift:
                self.task.send_key_up("lshift")

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

    def _post_skill_dodge(self):
        """Legacy method name: execute normal attacks after an E-only entry."""
        self.logger.info(f"{_LOG_PREFIX} post-skill normal attacks")
        self._checkpointed_dodge(self.POST_SKILL_DODGE_DURATION)

    def _execute_fallback_dodge(self):
        """Legacy method name: bounded normal attacks when Q/E are unavailable."""
        if self.is_dead or not self.is_current_char:
            self.logger.info(f"{_LOG_PREFIX} fallback attacks skipped (dead or not current)")
            return False

        self.logger.info(f"{_LOG_PREFIX} fallback normal attacks")
        self._checkpointed_dodge(self.FALLBACK_DODGE_DURATION)

        if not self.is_current_char or self.is_dead:
            self.logger.info(f"{_LOG_PREFIX} fallback dodge ended (char changed or dead)")
            return False

        return True

    def _checkpointed_dodge(self, duration) -> bool:
        """Legacy method name: normal attacks with frequent sound-check checkpoints."""
        deadline = self._now() + max(duration, 0)
        direction_key = self.DEFAULT_DIRECTION_KEY
        try:
            if direction_key is not None:
                self.task.send_key_down(direction_key)
                self.sleep(0.01)
            while self._now() < deadline:
                if not self.is_current_char or self.is_dead:
                    return False
                remaining = deadline - self._now()
                self._normal_attack_slice(min(self.ATTACK_SLICE_DURATION, remaining))
                self.sleep(0.01)
                self.check_combat()
        finally:
            if direction_key is not None:
                self.task.send_key_up(direction_key)
        return self.is_current_char and not self.is_dead

    def _normal_attack_slice(self, duration):
        if duration <= 0:
            return
        deadline = self._now() + duration
        while self._now() < deadline:
            if not self.is_current_char or self.is_dead:
                return
            self.normal_attack()
            remaining = deadline - self._now()
            if remaining > 0:
                self.sleep(min(self.NORMAL_ATTACK_INTERVAL, remaining))

    def _right_click_burst(self, duration):
        """持续右键点击 ``duration`` 秒，不管理方向键。"""
        if duration <= 0:
            return
        interval = self.DODGE_CLICK_INTERVAL
        start = self._now()
        while self._now() - start < duration:
            if not self.is_current_char or self.is_dead:
                return
            self.click(interval=interval, key="right")

    def _now(self):
        """可 patch 的时钟，供测试覆盖。"""
        return time.monotonic()

    def on_combat_end(self, chars):
        """战斗结束后清理。"""
        pass
