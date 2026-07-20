import time

from src.char.BaseChar import BaseChar
from src.combat.planner import CombatContext, Planner, RoleProfile
from src.combat.skill_cooldown import SkillCooldownModel


class Jiuyuan(BaseChar):
    SKILL_SETTLE_DURATION = 1.2
    # Anti-spam floor for tactical gather requests; tune with recordings [UNVERIFIED].
    GATHER_REUSE_INTERVAL = 8.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cooldowns = SkillCooldownModel(now_fn=lambda: self._now())

    def describe_role(self):
        from src.combat.team_strategies import is_chiz_abyss_team

        return RoleProfile(
            role=Planner.Role.SUB_DPS,
            field_preference=Planner.FieldPreference.SUB_DPS,
            combat_start_priority=100 if is_chiz_abyss_team(self.task.chars) else 0,
            max_field_time=1.0,
        )

    def gather_ready(self) -> bool:
        """Tactical-layer probe: skill up and reuse floor met (used by scatter-gather)."""
        return self.skill_available() and self._cooldowns.is_ready("gather")

    def combat_plan(self, context):
        ultimate = self.click_ultimate_action()

        def _execute_skill(_):
            result = self.click_skill(post_sleep=self.SKILL_SETTLE_DURATION)
            if result:
                self._cooldowns.mark_used("gather", self.GATHER_REUSE_INTERVAL)
            return result

        skill = self.planner_action(
            tags={Planner.ActionTag.SKILL_ACTION},
            slot=Planner.ActionSlot.SKILL,
            execute=_execute_skill,
            name=f"{self}_skill",
            reason="Jiuyuan skill with grouping settle",
            can_execute=lambda _: self.skill_available(),
            priority_ready=lambda _: self.skill_available(),
        )
        bullets = self.planner_action(
            tags=Planner.ActionTag.DEFAULT_ACTION,
            execute=self.fire_bullets,
        )

        def entry():
            skill_result = yield skill
            yield ultimate
            if not skill_result:
                yield bullets

        return self.plan(ultimate, skill, bullets, entry=entry)

    def fire_bullets(self, context: CombatContext = None):
        if context.has_strict_route():
            return
        box = self.task.box_of_screen(
            0.4191, 0.8799, 0.4348, 0.9076, name="jiuyuan_bullet", hcenter=True
        )
        if not self.has_bullets(box):
            return
        self.heavy_attack()
        return True

    def has_bullets(self, box):
        pct = self.task.calculate_color_percentage(bullet_color, box)
        return pct > 0.1

    def _now(self):
        return time.monotonic()


bullet_color = {
    "r": (97, 253),
    "g": (101, 181),
    "b": (168, 255),
}
