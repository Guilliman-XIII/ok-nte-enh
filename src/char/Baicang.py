import time

from src.char.BaseChar import BaseChar
from src.combat.planner import (
    ActionSlot,
    ActionTag,
    CombatContext,
    FieldPreference,
    FollowupStep,
    Role,
    RoleProfile,
)

_LOG_PREFIX = "[Baicang]"


class Baicang(BaseChar):
    """白藏 - 咒系(RED)主C，以闪避(右键)攻击为核心输出。

    结构参考 Nanally: E/Q 分离为 planner-visible action，
    Q 成功后进入角色专属爆发循环，循环内第二 E 检查 SKILL reservation。

    详细游戏机制见 docs/research/baicang.md。
    """

    MAX_FIELD_TIME = 0  # 禁止 Planner 通用平A fallback；白藏用专属 dodge action
    ULT_FIELD_DURATION = 8.0
    FALLBACK_DODGE_DURATION = 1.5
    DODGE_CLICK_INTERVAL = 0.12
    DODGE_SLICE_DURATION = 0.12
    SKILL_CHECK_INTERVAL = 1.5
    SECOND_SKILL_MODE = "observe"  # disabled | observe | execute
    SKILL_READY_STREAK_THRESHOLD = 3
    SKILL_SHORT_TIMEOUT = 2.0
    DEFAULT_DIRECTION_KEY = None  # 第一轮实机不按方向键，先验证右键本身有效
    POST_SKILL_DODGE_DURATION = 1.0  # E 成功但 Q 失败时的短右键输出
    ABYSS_OPENER_TIMEOUT = 20.0

    @staticmethod
    def is_abyss_team(chars):
        """仅识别用户固定的哈妮娅竞速队，不影响白藏的其他配队。"""
        from src.char.Daphneel import Daphneel
        from src.char.Hania import Hania
        from src.char.Sakiri import Sakiri

        required = (Baicang, Daphneel, Hania, Sakiri)
        return len(chars) == 4 and all(
            sum(isinstance(char, char_cls) for char in chars) == 1 for char_cls in required
        )

    def combat_policies(self, context: CombatContext) -> None:
        if not self.is_abyss_team(self.task.chars):
            return

        from src.char.Daphneel import Daphneel
        from src.char.Hania import Hania
        from src.char.Sakiri import Sakiri

        sakiri = next(char for char in self.task.chars if isinstance(char, Sakiri))
        hania = next(char for char in self.task.chars if isinstance(char, Hania))
        daphneel = next(char for char in self.task.chars if isinstance(char, Daphneel))
        route_started_at = None

        def route_expired():
            nonlocal route_started_at
            now = time.monotonic()
            if route_started_at is None:
                route_started_at = now
                return False
            return now - route_started_at >= self.ABYSS_OPENER_TIMEOUT

        context.request_route(
            [
                FollowupStep.for_action(
                    sakiri,
                    ActionSlot.SKILL,
                    reason="Sakiri groups enemies for Baicang opener",
                ),
                FollowupStep.for_action(
                    hania,
                    ActionSlot.ULTIMATE,
                    reason="Hania opens enhanced damage window",
                    optional=True,
                ),
                FollowupStep.for_action(
                    hania,
                    ActionSlot.SKILL,
                    reason="Hania deploys off-field damage",
                ),
                FollowupStep.for_action(
                    daphneel,
                    ActionSlot.SKILL,
                    reason="Daphneel primes dark burst before Baicang",
                ),
            ],
            reason="Baicang abyss opener",
            until=route_expired,
        )

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
            priority_ready=lambda _: self.skill_available(),
        )
        ultimate = self.click_ultimate_action(reason="baicang ultimate")
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

        - 方向键在整个循环期间持续按住（如果配置了）
        - 循环受 ``ULT_FIELD_DURATION`` 限时
        - 每个分片后检查: deadline、is_current_char、is_dead、check_combat
        - 第二 E 保护链仅在第一 E 真实成功时启用
        """
        self.logger.info(
            f"{_LOG_PREFIX} burst start (first_skill_succeeded={first_skill_succeeded})"
        )
        start = self._now()
        deadline = start + self.ULT_FIELD_DURATION
        direction_key = self.DEFAULT_DIRECTION_KEY

        track_second_skill = self.SECOND_SKILL_MODE != "disabled" and first_skill_succeeded
        cooldown_confirmed = False
        ready_streak = 0
        second_skill_done = False
        last_check = start

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
                slice_dur = min(self.DODGE_SLICE_DURATION, remaining)
                if slice_dur > 0:
                    self._right_click_burst(slice_dur)

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
        """E 成功但 Q 失败时的短右键输出，避免 E-only 路径无核心输出。"""
        self.logger.info(f"{_LOG_PREFIX} post-skill dodge (E ok, Q fail)")
        self._checkpointed_dodge(self.POST_SKILL_DODGE_DURATION)

    def _execute_fallback_dodge(self):
        """Q/E 均不可用时的兜底：有限时长的闪避攻击。"""
        if self.is_dead or not self.is_current_char:
            self.logger.info(f"{_LOG_PREFIX} fallback dodge skipped (dead or not current)")
            return False

        self.logger.info(f"{_LOG_PREFIX} fallback dodge")
        self._checkpointed_dodge(self.FALLBACK_DODGE_DURATION)

        if not self.is_current_char or self.is_dead:
            self.logger.info(f"{_LOG_PREFIX} fallback dodge ended (char changed or dead)")
            return False

        return True

    def _checkpointed_dodge(self, duration) -> bool:
        """以短分片输出右键，确保声音闪避/反击能通过 sleep checkpoint 抢占。"""
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
                self._right_click_burst(min(self.DODGE_SLICE_DURATION, remaining))
                self.sleep(0.01)
                self.check_combat()
        finally:
            if direction_key is not None:
                self.task.send_key_up(direction_key)
        return self.is_current_char and not self.is_dead

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
