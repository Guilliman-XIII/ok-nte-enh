# 双队深渊交接文档（2026-07-22）

> 上一份交接：`qwen_dual_abyss_handoff_20260721.md`。本文覆盖其后的全部改动与最新认知，**本文为准**。
> 阅读顺序建议：本文 → `docs/sound_dodge_counter_design.md`（声音闪避/反击的特意设计）→
> `docs/research/baicang.md`（白藏第二套手法）→ `docs/research/zzz_onedragon_reference.md`（一条龙参考，
> 含闪光分类器训练管线）→ `AGENTS.md`（项目铁律）。

## 0. 当前状态速览

- 分支：`feat/baicang-combat`
- **本轮所有改动均在工作区，尚未提交**（14 个修改 + 3 个删除已 staged + 1 个新测试文件）。
  最近一次提交是 `65c5b04`（实验性视觉引导+打散聚怪），**该功能本轮已整体删除**（见 §1）。
- 测试：全量 **426 passed, 0 failed**，另有 **8 个预存环境 ERROR**（中文路径装不了 ok 运行时，
  `Install dir ... must be an English path`，与战斗改动无关，勿误判回归）。ruff 全过。
- 白藏队：爆发已从"翻滚攻击"改为**第二套手法（点按两下再长按）**，用户实机三星通过。手法时序待录像精校。
- 小吱队：金谷颜色门控已按大招全程多帧校准，E 上限提到 8 次。仍待实机复核。
- 声音闪避：修了"双闸"漏闪 bug，闪避间隔 0.5→0.3s；蓄力反击默认打开（闪避优先级不变）。

## 1. 本次会话改动链（20260721 之后，全部未提交）

| 改动 | 内容 | 为什么 |
| --- | --- | --- |
| 删视觉引导+打散聚怪 | `git rm src/combat/enemy_field.py`、`TestEnemyField.py`、`TestScatterGather.py`；删 `team_strategies` 聚怪块、`AutoCombatTask` 两个配置项 | 视觉引导（朝怪群质心按 WASD）因镜头跟随产生 zigzag 无法调；怪散检测误触发、过度设计。实机失败，整体回退 |
| 白藏爆发改第二套手法 | `_perform_burst` 改为循环 `_heavy_combo`（点按普攻两下→长按重击后跳丢符→往前走重置）；删 `_single_roll`/`_steer_direction_key`/ROLL_*/STEER_* | 翻滚攻击（长按 lshift）实机判定为冲刺疾跑、零伤害，且需鼠标实时转向，自动化做不了。第二套手法只用普攻键+锁定朝向 |
| 小吱金谷颜色校准 | `yellow_pct_color` 放宽到 R185-255/G185-255/B95-175；`red_pct_color` 放宽到 R175-255/G60-145/B90-175 | 旧范围太窄，金色读数 R234G236B149、珊瑚红 R211G110B130 都匹配不到，闸门靠巧合工作。按大招 16 帧重校 |
| 小吱 E 上限 | 新增 `ULT_SKILL_MAX_USES=8`（独立于连携的 `SKILL_CHAIN_MAX_USES=3`） | 大招 8s 内 E 冷却快、充能回得快，旧的 3 次上限浪费充能 |
| 闪避间隔 0.5→0.3 | `DodgeCounterTrigger._min_dodge_interval=0.3` | 日志实测真攻击可 0.343s 连发，旧 0.5s 下限把第二次闪避跳了导致挨打 |
| 死代码清理 | 删 `Sakiri.gather_ready()`（保留 `_gather_reuse_ready`+`GATHER_REUSE_INTERVAL=10`）；拆九原 CD 脚手架（纯靠 `skill_available()` 门控） | 均为未接线的脚手架，删了不影响行为 |
| **声音双闸修复** | `SoundCombatContext.setup` 传 `is_allow_successive_trigger=True` | SoundListener 内部还有一道共享 0.5s 闸，会**静默吞掉** 0.5s 内的第二声攻击（无日志），且闪避/反击共用一个时间戳互相饿死。拆掉后 `DodgeCounterTrigger` 的 0.3s/1.0s 各管各的，成唯一闸 |
| **蓄力反击打开** | `config.py` 的 `Dodge All Attacks` 默认 True→False；两处 `.get(..., True)` 兜底同步改 False | 默认 True 时"敌人进蓄力该打它"的声音被半路改判成闪避，脚本从不 punish 蓄力。关掉后反击通道生效 |
| 新测试 | `tests/TestSoundTriggerWiring.py`（3 例）锁死上述两处声音修复 | 防回归 |

## 2. 核心机制与特意设计（最重要的持久知识）

### 2.1 白藏爆发 = 第二套手法，不是翻滚攻击

翻滚攻击（长按闪避那套）**已实测放弃**：按住方向键+长按 lshift 在游戏里是冲刺疾跑，白藏全程狂奔零伤害；
即便能搓出来也要全程按 W+鼠标实时转视角，自动化做不了。

当前采用攻略 BV1Wy9bBWESK 的第二套手法：点按普攻两下 → 长按普攻（后跳丢符、伤害高）→ 往前走一段重置
连招段数（避开低伤的第四五段）→ 循环。**全程只用普攻键，锁定目标保证朝向，不用闪避键、不用鼠标转向。**
机制细节与待测参数见 `docs/research/baicang.md`。

### 2.2 小吱金谷 = 正负摆动的时机闸门

小吱大招期间血条上方有个"金谷"百分比进度条，**正负摆动**：正数显示金黄字（该放 E），负数显示珊瑚红字
（别放 E）。`yellow_pct > red_pct` 这道闸门**就是放 E 的时机机制本身**——体现"宁可少放也别乱放"。
颜色范围已按大招全程 16 帧校准（正数 5 帧全开门、负数 10 帧全关门），黄红靠绿色通道隔离（黄 G≥185、红 G≤145）。
闸门框 `box_of_screen(0.487, 0.775, 0.514, 0.798)`。

### 2.3 声音闪避/反击（详见 `docs/sound_dodge_counter_design.md`）

- **闪避是命根子，反击只是锦上添花**（用户明确：三下就死）。任何改动不得降低闪避可靠性。
- 听觉是模板匹配：`dodge.wav`（敌人要动手的声音）/ `counter.wav`（敌人进蓄力的声音）两段参考音，
  每 0.025s 截 0.2s 实时声音算归一化互相关，谁过阈值触发谁（闪避 0.13、反击 0.12）。**闪避音永远先判。**
- 双闸已拆：`is_allow_successive_trigger=True`，唯一闸是 `DodgeCounterTrigger`（闪避 0.3s / 反击 1.0s）。
- 反击默认开（`Dodge All Attacks=False`），但闪避优先级不变（先判+共享执行锁里闪避不让反击）。

### 2.4 视觉闪避：已研究，搁置待命

一条龙闪避强在"视觉+听觉双信号"。我们已研究并证实敌人受击前 ~0.4-0.5s 冒纯红光（R>170,G<110,B<110，
中央亮红占比从 0.06% 飙到 0.59%），但**全屏红色底噪随场景差异巨大**（另一段录像底噪 0.08-1.96%），
粗测全区域不可靠。落地路线：聚焦现有 YOLO 敌框（`CombatCheck.find_target` 战斗时持续在跑，读
`latest_results` 即可，不用新模型）+ 相对自身基线突变，与听觉取或。**先离线回放拿误报/漏报数据再上真机。**

一条龙的视觉是一只 YOLOv8n 闪光分类器（3 类：无/红光闪避/黄光格挡），数据集 `ZZZ-FlashClassify` 托管在
ModelScope，由 OneDragon-Anything 组织集中训练、release 分发，**绝区零美术专用，不可迁移异环**。训分类器是
"数据工程"不是"代码工程"，最贵的是攒异环自己的标注截图，没法白嫖速成——**用户已决定分类器搁置**，先用听觉+开反击。
详见 `docs/research/zzz_onedragon_reference.md` 的"闪光分类器训练管线"一节。

## 3. 设计不变量与关键决策

- **闪避优先级绝对**：声音链路里闪避音先判；反击默认开但不得挤占闪避。改声音触发前先读 `docs/sound_dodge_counter_design.md`。
- **Q 先手**：白藏、哈妮娅、达芙蒂尔入场先 Q。**E 先手聚怪**：早雾、九原入场先 E 再 Q。
- **`SECOND_SKILL_MODE="execute"`**（白藏）：⚠️ 偏离 `AGENTS.md` 默认 `observe`。用户明确"技能好了要放"，
  爆发内 E 真正释放。若发现误放需回退，改回 `observe`。
- **严格队伍绑定 fail-closed**：换队后绝不操作新队；部分识别已知深渊阵容不发通用输入，稳定窗口重试；
  只有真正未知的新战斗才走通用检测。
- **视觉引导/打散聚怪已删除，勿重新引入**（镜头跟随致 zigzag、怪散检测误触发，实测失败）。
- **早雾 `GATHER_REUSE_INTERVAL=10s`** 是后续波次重聚怪的关键，`can_execute`/`priority_ready` 在用，勿删。
- 未验证机制只写 `docs/research/*.md` 并标 `[EXTERNAL]`/`[UNVERIFIED]`，类 docstring 只陈述事实并指向研究文档。

## 4. 当前两队战斗逻辑（实现现状）

### 白藏队

入场（`Baicang.combat_plan` 的 entry）：**Q 先手**。Q 成功 → `_perform_burst`；失败 → E → `_post_skill_dodge`；
都失败 → `fallback_dodge`。

`_perform_burst`（`ULT_FIELD_DURATION=12s`）循环：每轮 `_heavy_combo`（点按 `HEAVY_TAP_COUNT=2` 下、间隔
`HEAVY_TAP_INTERVAL=0.18` → `heavy_attack(HEAVY_HOLD_DURATION=0.6)` 长按重击 → `_walk_forward_reset` 按 W
走 `WALK_RESET_DURATION=0.4` 重置，方向键 try/finally 释放）→ `check_combat` → 每 `ARC_CHECK_INTERVAL=2.0s`
放 R → E 按 streak 释放（`SKILL_CHECK_INTERVAL=0.8`，连续 `SKILL_READY_STREAK_THRESHOLD=2` 次就绪才放，
放完 streak 归零可再放，走 `_try_second_skill` 的 `can_execute_action` 正规通道）。

开场路线（`team_strategies.request_baicang_opener`，全 optional，24s 超时）：
```
早雾 E(聚怪) → 早雾 Q(压制+加攻) → 哈妮娅 Q → 哈妮娅 E → 达芙蒂尔 E → 达芙蒂尔 Q → 回白藏
```

### 小吱队

开场（`request_chiz_route(opener=True)`）：`九原 E(聚怪) → [零 Q] → 零 E → 回小吱`。
循环（`opener=False`）：`小吱站场等创生 → 九原(创生入场) → 九原 E(聚怪) → [九原 Q] → [零 Q] → 零 E
→ 翳(延滞入场) → [翳 Q] → 翳 E → [九原 E] → 回小吱`。

小吱大招内 E：金谷颜色门控（`yellow_pct >= SKILL_GAUGE_MIN_YELLOW=0.02 且 yellow_pct > red_pct`），
最多 `ULT_SKILL_MAX_USES=8` 次，间隔 ≥`SKILL_CHAIN_MIN_E_INTERVAL=0.6s`。非大招技能链：两平 A → 一 E，
最多 `SKILL_CHAIN_MAX_USES=3` 次。

## 5. 待验证项（全部需实机/录像，脚本无法自证）

| 项 | 现状 | 怎么验 |
| --- | --- | --- |
| 白藏第二套手法时序 | `HEAVY_HOLD_DURATION=0.6`/`WALK_RESET_DURATION=0.4`/`HEAVY_TAP_INTERVAL=0.18` 全 UNVERIFIED | 录像逐帧对，常量都在 `Baicang.py` 顶上，调一个数即可 |
| 红蝴蝶 E 时机 | 未专门处理 | 是否要在长按蓄力后立刻放 E 吃最高伤害（用户已同意方向，未实现） |
| 小吱颜色校准 | 按录像帧校准，非游戏内实时 | 实机大招看 E 是否在金字时放、红字时不放 |
| 闪避间隔 0.3 | 按日志数据选的 | 实机看快连招第二次能否闪掉、是否多闪回声 |
| 蓄力反击 | 默认刚打开 | 实机看敌人蓄力时脚本是否普攻一下打出"嘣" |

## 6. 下一步

1. **用户实机测试本轮改动**（白藏手法、小吱金谷、闪避 0.3、蓄力反击），拿录像/日志回来再调。
2. **视觉闪避**：方案已定（YOLO 敌框+相对基线突变+与听觉取或+先离线回放），**等用户发话再实现**，不抢跑。
3. **红蝴蝶 E 时机**：用户已同意"长按蓄力后放 E"，与白藏手法校准一起做。
4. **闪光分类器**：搁置（数据工程、绝区零专用不可迁移、无捷径）。颜色启发式是它的必经之路（先建共用管线+顺手攒数据）。
5. 上下文维持，继续"边做边存档（git/docs/memory）+ 阶段交接文档"节奏。

## 7. 关键文件索引

| 文件 | 作用 |
| --- | --- |
| `src/char/Baicang.py` | 白藏：Q 先手、第二套手法爆发（`_heavy_combo`/`_walk_forward_reset`）、E/R 周期释放 |
| `src/char/Sakiri.py` | 早雾：长按 E 聚怪、`GATHER_REUSE_INTERVAL=10`、开场可放 Q |
| `src/char/Jiuyuan.py` | 九原：E 先手入场，纯 `skill_available()` 门控 |
| `src/char/Chiz.py` | 小吱：金谷门控 E（`ULT_SKILL_MAX_USES=8`）、校准后的黄/红颜色范围 |
| `src/char/Hania.py` / `Daphneel.py` | 哈妮娅（Q 先手、E 后 0.3s 切出）/ 达芙蒂尔（Q 先手短切） |
| `src/combat/team_strategies.py` | 两队开场/循环路线（`request_baicang_opener`/`request_chiz_route`） |
| `src/sound_trigger/SoundListener.py` | 听觉模板匹配（dodge.wav/counter.wav 归一化互相关） |
| `src/sound_trigger/SoundCombatContext.py` | 声音抢占编排，`is_allow_successive_trigger=True`、counter 路由 |
| `src/sound_trigger/DodgeCounterTrigger.py` | 闪避/反击执行 + 唯一间隔闸（0.3s/1.0s） |
| `src/combat/BaseCombatTask.py` | 声音配置应用、P0 部分识别探针 |
| `src/config.py` | `Dodge All Attacks` 默认 False 等全局配置 |
| `docs/sound_dodge_counter_design.md` | 声音闪避/反击特意设计（持久） |
| `docs/research/baicang.md` | 白藏第二套手法机制（EXTERNAL） |
| `docs/research/zzz_onedragon_reference.md` | 一条龙参考 + 闪光分类器训练管线（EXTERNAL） |
| `tests/TestBaicang.py` / `TestAbyssTeams.py` / `TestSoundTriggerWiring.py` | 战斗 + 声音回归测试 |

## 8. 运行与测试备忘

- venv 解释器（bash 里必须用正斜杠）：`./.venv/Scripts/python.exe`
- 全量测试：`./.venv/Scripts/python.exe -m unittest discover -s tests -p "*.py"`（426 passed + 8 环境 ERROR）
- 声音测试：`./.venv/Scripts/python.exe -m unittest tests.TestSoundTriggerWiring -v`
- ruff：`./.venv/Scripts/python.exe -m ruff check <改动文件>`
- 日志：`logs/ok-script.log`（按天归档 `ok-script.YYYY-MM-DD.log`，当前 log 只留最近几分钟）。
  录像文件名含起始时间，`录像内秒数 = 日志时间戳 - 录像起始时间`。排查"不放技能"先搜 planner 的 `strict route`。
- 不要提交 `custom_chars/db.json`、logs、录像、本机个人路径。
