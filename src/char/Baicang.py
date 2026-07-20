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

    Shift-AOE hypothesis [UNVALIDATED - requires live recording verification]:
      During Q burst, holding a direction key (e.g. "w") makes Baicang advance
      through grouped enemies, extending AOE coverage. Periodic Shift taps may
      trigger dash-attacks for additional damage. Set BURST_DIRECTION_KEY to
      enable direction holding during burst; set SHIFT_DASH_INTERVAL > 0 to add
      periodic Shift taps. Both are disabled by default until a version-bound
      recording confirms the input sequence produces the intended visual result
      without conflicting with sound-triggered dodge.

    Verification checklist before enabling:
      1. 120 FPS recording of manual Shift-held AOE showing dash-attack triggers.
      2. Measured minimum Shift tap duration and interval for reliable dash.
      3. Confirmation that direction key hold does not interfere with dodge input.
      4. 10 consecutive successful burst windows with Shift-AOE enabled.
    """

    MAX_FIELD_TIME = 0
    ULT_FIELD_DURATION = 12.0
    FALLBACK_DODGE_DURATION = 1.5
    NORMAL_ATTACK_INTERVAL = 0.18
    ATTACK_SLICE_DURATION = 0.36
    DODGE_CLICK_INTERVAL = 0.12
    DODGE_SLICE_DURATION = 0.12
    SKILL_CHECK_INTERVAL = 1.5
    SECOND_SKILL_MODE = "observe"  # disabled | observe | execute
    SKILL_READY_STREAK_THRESHOLD = 3
    SKILL_SHORT_TIMEOUT = 2.0
    DEFAULT_DIRECTION_KEY = None
    BURST_DIRECTION_KEY = None  # e.g. "w" to hold forward during Q burst [UNVALIDATED]
    SHIFT_DASH_INTERVAL = 0.0  # seconds between Shift taps during burst; 0 = disabled
    SHIFT_DASH_DURATION = 0.08  # Shift key hold duration per tap
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
            skill_result = yield skill
            if skill_result and self.ultimate_available():
                self.sleep(0.3)

            ultimate_result = yield ultimate
            if ultimate_result:
                self._perform_burst(context, first_skill_succeeded=bool(skill_result))
                return

            if skill_result:
                self._post_skill_dodge()
            else:
                yield fallback_dodge

        return self.plan(skill, ultimate, fallback_dodge, entry=entry)

    def _perform_burst(self, context: CombatContext = None, first_skill_succeeded: bool = False):
        """Q 成功后的爆发输出循环 (参考 Nanally.perform_in_ult)。

        - BURST_DIRECTION_KEY (或 DEFAULT_DIRECTION_KEY) 在整个循环期间持续按住
        - SHIFT_DASH_INTERVAL > 0 时周期性点按 Shift 触发冲刺 [UNVALIDATED]
        - 循环受 ``ULT_FIELD_DURATION`` 限时
        - 每个分片后检查: deadline、is_current_char、is_dead、check_combat
        - 第二 E 保护链仅在第一 E 真实成功时启用
        """
        self.logger.info(
            f"{_LOG_PREFIX} burst start (first_skill_succeeded={first_skill_succeeded})"
        )
        start = self._now()
        deadline = start + self.ULT_FIELD_DURATION
        direction_key = self.BURST_DIRECTION_KEY or self.DEFAULT_DIRECTION_KEY
        shift_dash_enabled = self.SHIFT_DASH_INTERVAL > 0 and direction_key is not None

        track_second_skill = self.SECOND_SKILL_MODE != "disabled" and first_skill_succeeded
        cooldown_confirmed = False
        ready_streak = 0
        second_skill_done = False
        last_check = start
        last_dash = start

        try:
            if direction_key is not None:
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
                slice_dur = min(self.ATTACK_SLICE_DURATION, remaining)
                if slice_dur > 0:
                    self._normal_attack_slice(slice_dur)

                if shift_dash_enabled and self._now() - last_dash >= self.SHIFT_DASH_INTERVAL:
                    last_dash = self._now()
                    self.task.send_key_down("lshift")
                    self.sleep(self.SHIFT_DASH_DURATION)
                    self.task.send_key_up("lshift")

                self.sleep(0.01)
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
            if direction_key is not None:
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
