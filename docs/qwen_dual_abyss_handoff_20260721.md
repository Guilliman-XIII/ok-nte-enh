# 双队深渊交接文档（2026-07-21）

> 上一份交接：`qwen_dual_abyss_handoff_20260720.md`。本文覆盖其后的全部改动与最新认知。
> 阅读顺序建议：本文 → `docs/research/baicang.md`（白藏翻滚攻击机制）→
> `docs/research/team_axis_design.md`（两队设计原则）→ `AGENTS.md`（项目铁律）。

## 0. 当前状态速览

- 分支：`feat/baicang-combat`
- 最新提交：`7902db7`（白藏爆发改翻滚攻击）
- 战斗相关测试：`tests/TestBaicang.py + TestAbyssTeams.py + TestCombatPlanner.py + TestTeamPresetGuard.py`
  共 **166 passed, 9 subtests passed**，ruff 全过。
- 白藏队：低压 Go，高压 Conditional Go，**翻滚攻击待录像验证**。
- 小吱队：仍为实机 No-Go / 待验证；本轮只修了九原循环聚怪 bug，小吱本人手法尚未按攻略校准。
- 全量 pytest 有 **43 个预存失败**，全部是 ASCII junction `D:\ok-nte-dev` 中文路径编码导致
  图片加载 `ValueError: Could not read image`，与战斗改动无关，勿误判为回归。

## 1. 本次会话改动链（按提交，旧→新）

| 提交 | 内容 |
| --- | --- |
| `67da8a5` | **P0 修复**：部分识别已知深渊阵容时不再回退通用检测，改为稳定窗口重试；加 Shift-AOE 脚手架 |
| `4135d52` | 启用白藏 Shift-AOE（当时是按住 W+周期点 Shift，后来证明理解错了）；早雾多波次重聚 |
| `539f706` | 白藏爆发内真正放 E/R；聚怪间隔 18s→10s |
| `af7b5d2` | 白藏改 Q 先手入场；哈妮娅 E 后等待 0.5s→0.3s |
| `f286635` | 修爆发内 E 逻辑：Q 先手后 E 就绪也能放、可多次放（移除 cooldown_confirmed / second_skill_done） |
| `95fe77e` | Shift-AOE 改成"全程按住"并默认关闭（用户说要先教正确手法） |
| `7cd55b7` | 攻略素材入库（字幕 + videos，视频不入 git） |
| `5f3d64b` | **聚怪优先**：九原循环补 E 聚怪步、九原入场改 E 先手、早雾开场补 Q |
| `7902db7` | **白藏爆发改翻滚攻击**（替代会打散怪的普攻） |

## 2. 从攻略学到的核心机制（最重要的持久知识）

来源：UP 主"打游戏的老二"，视频 `BV1dB5Y6xE2q`（白藏）、`BV16o5P6DEru`（早雾）、
`BV1vHLb61Ewb`（达芙蒂尔）。字幕在 `docs/research/source_guides/`。全部标 `[EXTERNAL]`，
**尚未录像验证**。

### 2.1 白藏核心输出 = 翻滚攻击，不是普攻

- 普攻会把怪打散（第 2 段击退、第 5 段炸飞）——用户实机观察与攻略一致。
- **翻滚攻击**：按住方向键不松 → 长按闪避→松开→再长按闪避→松开，循环释放。每次翻滚丢 3 个红字，
  砸地+爆炸两段伤害。方向键按住保证每次往前走一步不打空。
- 用户实战按 **A 键原地转身扫圈**（不是按 W 前冲）。
- 翻滚/转身本质都是**闪避**，有无敌帧；**消耗体力**，体力耗尽不能再翻滚（攻略建议改用长按普攻，
  但脚本无体力读数，暂未处理）。
- 白藏 E 有三形态：普通(白图标，独立 CD)、对单(红爆炸，点按闪避后可放，挂禁制)、
  对群(红蝴蝶，打出"丢 3 字"招式后可放，挂励志)。**对单与对群共享 CD**。群怪放对群。
- 言灵字（注/禁/励）在开大时触发；攻略最优是"攒 3 个字再开大"，但需要识别场上字数（脚本暂无此能力，
  故当前仍用 Q 先手的简化版）。

### 2.2 早雾：长按 E 聚怪，群怪手法是 E→Q

- **长按 E**（非点按）：范围浮空 + 触发被动二降防 10% + 回更多环合值。点按只是击倒，吃不到降防。
  当前实现 `SKILL_HOLD_DURATION=0.8` 长按，选择正确。
- 群怪开场：长按 E 聚怪 → 开大压制 + 给全队 30% 攻击加成 → 切队友。

### 2.3 待录像实测的参数（脚本无法从攻略拿到精确值）

| 参数 | 当前值 | 需验证 |
| --- | --- | --- |
| `ROLL_DODGE_HOLD` | 0.25s | 触发翻滚而非点按闪避的最短按住时长（**纯猜测，最关键**） |
| `ROLL_INTERVAL` | 0.12s | 两次翻滚间的松手-再按节奏 |
| `BURST_DIRECTION_KEY` | "a" | 按 A 是原地转身还是左移，是否真能扫圈 |
| 体力耗尽 | 未处理 | 耗尽后翻滚是否静默失败、是否要切长按普攻 |

## 3. 当前白藏队战斗逻辑（实现现状）

入场顺序（`Baicang.combat_plan` 的 entry）：**Q 先手**。
- Q 成功 → `_perform_burst`（翻滚攻击循环）
- Q 失败 → E → `_post_skill_dodge`（1s 普攻）
- 都失败 → `fallback_dodge`（1.5s 普攻）

`_perform_burst`（`ULT_FIELD_DURATION=12s`）：
- 全程按住 A（`try/finally` 释放，符合 AGENTS.md 方向键铁律）
- 循环调用 `_single_roll`：`send_key_down("lshift")` → sleep `ROLL_DODGE_HOLD` → `send_key_up("lshift")`
  （闪避键自身也有 `try/finally` 保证释放）→ sleep `ROLL_INTERVAL`
- 每 `ARC_CHECK_INTERVAL=2.0s` 放一次 R（专武）
- E 用 streak 检测（`SKILL_CHECK_INTERVAL=0.8s`，连续 `SKILL_READY_STREAK_THRESHOLD=2` 次就绪才放，
  放完 streak 归零可再放）

开场路线（`team_strategies.request_baicang_opener`，全部 optional，24s 超时）：
```
早雾 E(聚怪) → 早雾 Q(压制+加攻) → 哈妮娅 Q → 哈妮娅 E → 达芙蒂尔 E → 达芙蒂尔 Q → 回白藏
```

## 4. 当前小吱队战斗逻辑（实现现状）

开场路线（`request_chiz_route(opener=True)`）：
```
九原 E(聚怪) → [零 Q] → 零 E → 回小吱
```
循环路线（`opener=False`，本轮已修）：
```
小吱站场等创生 → 九原(创生入场) → 九原 E(聚怪,新增) → [九原 Q] → [零 Q] → 零 E
→ 翳(延滞入场) → [翳 Q] → 翳 E → [九原 E] → 回小吱
```
小吱大招内 E 用金谷颜色门控（`yellow_pct >= SKILL_GAUGE_MIN_YELLOW=0.02 且 yellow_pct > red_pct`），
最多 3 次，间隔 ≥0.6s。非大招技能链：两次平 A → 一次 E，最多 3 次。

## 5. 设计不变量与关键决策

- **严格队伍绑定 fail-closed**：旧队伍绝不在换队后操作新队伍；部分识别已知深渊阵容不发通用输入；
  真正未知的新战斗才走通用检测（`test_auto_mode_keeps_generic_detection_for_a_new_unmatched_battle` 守护）。
- **Q 先手**：白藏、哈妮娅、达芙蒂尔入场先 Q（哈妮娅/达芙蒂尔本就是 Q 先手，白藏本轮改的）。
- **E 先手聚怪**：早雾、九原入场先 E 聚怪再 Q（用户明确建议 + 攻略支持）。
- **`SECOND_SKILL_MODE="execute"`**：⚠️ 偏离 `AGENTS.md` 默认 `observe`。用户明确要求"技能好了要放"，
  故白藏爆发内 E 改为真正释放。若后续发现误放需回退，改回 `observe`。
- 未验证机制只写 `docs/research/*.md` 并标 `[EXTERNAL]`/`[UNVERIFIED]`，类 docstring 只陈述事实并指向研究文档。

## 6. 下一步

1. **用户正在找小吱 + 九原的攻略视频**（UP 主"打游戏的老二"，合集里有 `【1.0】小吱`、`【1.0】九原`）。
   拿到后按白藏/早雾的方式提取机制，校准小吱队（当前 No-Go）。
2. **白藏翻滚攻击必须录像验证**：重点看 `ROLL_DODGE_HOLD=0.25` 是否真触发翻滚、按 A 是否原地转圈、
   体力耗尽表现。对着录像调这三个参数。
3. 安魂曲攻略**不需要**（用户没有安魂曲，三个辅助与白藏队重合且已有各自攻略）。
4. 上下文维持 400K，不拉长；继续用"边做边存档（git/docs/memory）+ 阶段交接文档"的节奏。

## 7. 关键文件索引

| 文件 | 作用 |
| --- | --- |
| `src/char/Baicang.py` | 白藏：Q 先手入场、翻滚攻击爆发、E/R 周期释放 |
| `src/char/Sakiri.py` | 早雾：长按 E 聚怪、`GATHER_REUSE_INTERVAL=10`、开场可放 Q |
| `src/char/Jiuyuan.py` | 九原：E 先手入场 |
| `src/char/Chiz.py` | 小吱：金谷门控 E、`SKILL_GAUGE_MIN_YELLOW=0.02` |
| `src/char/Hania.py` | 哈妮娅：Q 先手、E 后 0.3s 切出 |
| `src/char/Daphneel.py` | 达芙蒂尔：Q 先手短切爆发 |
| `src/combat/team_strategies.py` | 两队开场/循环路线定义 |
| `src/combat/BaseCombatTask.py` | P0 部分识别探针 `_probe_visible_team` / `_stabilize_partial_recognition` |
| `src/char/custom/CustomCharManager.py` | `partial_preset_match_count` |
| `docs/research/baicang.md` | 白藏翻滚攻击机制（EXTERNAL） |
| `docs/research/source_guides/` | 攻略字幕 + 视频（视频不入 git） |
| `tests/TestBaicang.py` 等 | 战斗回归测试 |

## 8. 运行与测试备忘

- ASCII junction：`D:\ok-nte-dev`（指向中文路径项目目录）。
- 跑战斗测试：
  `D:\ok-nte-dev\.venv\Scripts\python.exe -m pytest tests/TestBaicang.py tests/TestAbyssTeams.py tests/TestCombatPlanner.py tests/TestTeamPresetGuard.py -q`
- ruff：`... -m ruff check src/char/Baicang.py src/char/Sakiri.py src/char/Jiuyuan.py src/combat/team_strategies.py`
- 日志：`logs/ok-script.log`。排查"角色不放技能"先搜 planner 的 `strict route` 步骤
  （九原循环不放 E 就是这么查出来的：循环 route 只排了创生入场+大招，没有 E 聚怪步）。
- 不要提交 `custom_chars/db.json`、logs、录像、本机个人路径。
