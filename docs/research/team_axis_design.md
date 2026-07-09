# 队伍轴设计研究

> 基于 Hotori 队伍轴模式分析，规划 P5 阶段的四人队伍轴实现方案。

## Hotori 模式分析

### 核心 API

| API | 用途 | 生命周期 |
| --- | --- | --- |
| `combat_policies(context)` | 队伍加载时发布常驻 reservation | 整场战斗 |
| `context.reserve_actions(reservations, reason, until, on_finish)` | 保留队友动作槽位 | until 条件过期 |
| `context.request_route(steps, reason, until, on_finish)` | 固定顺序协作路线 | until 条件过期 |
| `context.request_switch(char, reason, until)` | 请求切人 | until 条件过期 |
| `FollowupStep.for_action(char, slot, reason, optional)` | 路线步骤：角色执行某 slot | 路线内 |
| `FollowupStep.for_entry_reaction(char, reason)` | 路线步骤：入场反应 | 路线内 |
| `ActionReservation.for_action(char, slot)` | 动作保留：防止其他角色使用 | until 条件过期 |
| `FieldClaim.high(reason, expected_entry)` | 入场诉求：提高切人评分 | 单次入场 |
| `Planner.NEVER_EXPIRES` | 永不过期 | 整场战斗 |

### Hotori 实现要点

1. **`combat_policies()`**：识别队伍中的 Zero 和 Nanally，为 Zero 的 SKILL 槽位发布常驻 reservation
2. **`combat_plan()`**：
   - `ultimate` action：Q 成功后发布后续 reservation 和 request_switch
   - `setup` action：E 成功后发布 record window route
3. **`_execute_hotori_setup()`**：
   - E 成功后调用 `context.request_route(steps)` 创建协作路线
   - 路线步骤按顺序执行：队友 Q → 队友 E → Nanally 入场反应
   - 同时发布 `record_window_holds` reservation 保护路线中的动作
4. **`_execute_hotori_ultimate()`**：
   - Q 成功后发布 `after_ultimate_reservations`
   - 通过 `context.request_switch(team.zero)` 请求切换到 Zero
5. **数据结构**：`HotoriRecordPlan` dataclass 集中管理路线步骤和 reservation

## 目标队伍轴设计

### 队伍轮转

```
哈妮娅(Q→E) → 阿德勒(叠业→E→Q) → 达芙蒂尔(Q→E→爆发) → 白藏(E→Q→闪避输出)
```

### 各角色队伍轴职责

#### 哈妮娅 (SUB_DPS, 开场角色)

```python
def combat_policies(self, context):
    # 常驻：保护主C的 SKILL 槽位
    if self._find_main_dps():
        context.reserve_actions(
            [ActionReservation.for_action(main_dps, ActionSlot.SKILL)],
            reason="hania protects main_dps skill",
            until=Planner.NEVER_EXPIRES,
        )

def _execute_hania_setup(self, context):
    # Q+E 成功后发布 buff window
    if context is not None:
        context.request_switch(
            self._find_next_support(),  # Adler
            reason="hania buff deployed, switch to next support",
        )
```

#### 阿德勒 (SUB_DPS)

```python
def _execute_adler_setup(self, context):
    # 叠业+E+Q 成功后发布 shield window
    if context is not None:
        context.request_switch(
            self._find_main_dps(),  # Daphneel or Baicang
            reason="adler shield deployed, switch to main_dps",
        )
```

#### 达芙蒂尔 (MAIN_DPS, 第二输出)

```python
# Daphneel 接受 support 的 request_switch 进入爆发
# 无需主动发布 request，由 planner 的 request lifecycle 驱动
# burst 结束后 on_combat_end → switch_other_char
```

#### 白藏 (MAIN_DPS, 最终主C)

```python
# Baicang 作为最终主C，接受所有 support 完成后的切人
# 使用 FieldClaim.high 在 burst window 时抢回场
def combat_plan(self, context):
    claims = []
    if self.ultimate_available():
        claims.append(
            FieldClaim.high(
                reason="baicang burst window",
                expected_entry=ExpectedEntry(slot=ActionSlot.ULTIMATE),
            )
        )
    return self.plan(skill, ultimate, fallback_dodge, claims=claims, entry=entry)
```

### 实现路线图

1. **第一步：Hania + Adler 接入 `request_switch`**
   - 在 E/Q 成功后调用 `context.request_switch(next_char, reason)`
   - 添加 `_find_main_dps()` / `_find_next_support()` 辅助方法
   - 添加测试：验证 request_switch 被正确发布

2. **第二步：Hania 接入 `combat_policies`**
   - 发布常驻 reservation 保护主C SKILL 槽位
   - 添加测试：验证 reservation 被正确发布

3. **第三步：Baicang 接入 `FieldClaim`**
   - burst window 时发布 FieldClaim.high
   - 添加测试：验证 claim 在正确条件下发布

4. **第四步：队伍轴集成测试**
   - 使用真实 `CombatPlanner` 模拟四人轮转
   - 验证切人顺序、request 生命周期、reservation 保护
   - 验证失败 fallback 路径

### 风险与限制

- **实机未验证**：所有队伍轴设计基于代码分析，未经实机验证
- **角色识别**：`_find_main_dps()` 需要遍历 `self.task.chars` 按 `Role.MAIN_DPS` 识别
- **request 生命周期**：`until` 条件需要仔细设计，避免永久阻塞
- **planner 调度**：planner 的切人评分可能与 request 冲突，需要实机调试
- **复杂度**：队伍轴实现显著增加代码复杂度，需要充分测试

### 依赖

- `FollowupStep`, `ActionReservation`, `FieldClaim`, `ExpectedEntry` 从 `src.combat.planner` 导入
- `Planner.NEVER_EXPIRES` 常量
- `CombatContext.request_route()`, `request_switch()`, `reserve_actions()`
