# OKNTE 战斗逻辑补充深度审查报告

审查日期：2026-07-10  
审查对象：`feat/baicang-combat` 分支的战斗逻辑补充  
项目定位：基于 GitHub 开源项目 OKNTE 的《异环》自动战斗与角色逻辑扩展

> 2026-07-16 复审说明：第 2-8 节保留为 2026-07-10 的历史快照。此后分支已完成
> 白藏 route 目标动作安全修正、删除无条件 `FieldClaim.high`、新角色 route 安全修正和真实
> `CombatPlanner` 集成测试等工作。当前战略结论与双队路线以第 10 节及
> `docs/research/team_axis_design.md` 为准。

## 1. 审查背景

OKNTE 是一款基于图像识别和 `ok-script` 框架的《异环》自动化工具，核心能力包括后台运行、一键日常、自动战斗、角色中心、特征管理、声音驱动闪避/反击等。自动战斗不是单纯宏脚本，而是依赖：

- 角色中心识别当前队伍角色。
- 特征管理适配不同角色/皮肤。
- `BaseCombatTask` 负责战斗状态、CD、按键、切人、识别等基础能力。
- `CombatPlanner` 负责任务级战斗决策、动作声明、切人评分、协作请求、slot reservation。
- 各角色类通过 `describe_role()` 和 `combat_plan(context)` 声明自身定位、动作和入场流程。

因此，本项目的正确发展方向不是堆叠硬编码按键序列，而是把新角色逻辑纳入 OKNTE 现有 planner 语义，让动作、资源槽位、队伍轴和失败回退都能被统一调度。

## 2. 当前分支状态

当前 Git 状态显示：

- 分支：`feat/baicang-combat`
- 已修改：`src/char/CharFactory.py`
- 新增：`PROJECT_RULES.md`
- 新增角色：`src/char/Baicang.py`、`src/char/Adler.py`、`src/char/Daphneel.py`、`src/char/Hania.py`
- 新增测试：`tests/TestBaicang.py`、`tests/TestNewChars.py`

新增角色已注册到 `CharFactory.char_dict`：

- `char_baicang`：白藏，`Element.RED`
- `char_adler`：阿德勒，`Element.RED`
- `char_daphneel`：达芙蒂尔，`Element.PURPLE`
- `char_hania`：哈妮娅，`Element.BLUE`

## 3. 验证结果

已完成以下本地验证：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\TestBaicang.py tests\TestNewChars.py tests\TestCombatPlanner.py -q
```

结果：

- 159 passed

```powershell
.\.venv\Scripts\python.exe -m unittest tests.TestBaicang tests.TestNewChars tests.TestCombatPlanner -v
```

结果：

- Ran 159 tests
- OK

```powershell
.\.venv\Scripts\python.exe -m ruff check src\char\Baicang.py src\char\Adler.py src\char\Daphneel.py src\char\Hania.py src\char\CharFactory.py tests\TestBaicang.py tests\TestNewChars.py
```

结果：

- All checks passed

```powershell
.\.venv\Scripts\python.exe -m ruff format --check src\char\Baicang.py src\char\Adler.py src\char\Daphneel.py src\char\Hania.py src\char\CharFactory.py tests\TestBaicang.py tests\TestNewChars.py
```

结果：

- 7 files already formatted

全量 `unittest discover` 在 124 秒后超时，未观察到明确失败用例。结合测试文件扫描，原因更可能是全量测试中存在硬件/音频/图像/异步等待类慢测试，而不是新增角色单元测试失败。

## 4. 总体评价

当前方向是正确的。项目已经选择接入 OKNTE 的 `CombatPlanner`，通过角色的 `combat_plan()` 声明 `ActionIntent`，而不是绕开框架直接写死按键。这一点非常关键。

其中 `Baicang` 的实现质量明显高于其他三个新增角色。它已经考虑了：

- E/Q 拆成 planner-visible actions。
- fallback dodge 不伪造 skill/ultimate 成功。
- fallback action 的 `priority_ready=False`，避免吸引切人评分。
- Q 成功后进入角色专属 burst。
- burst 中方向键使用 `try/finally` 释放。
- 第二 E 使用 `disabled | observe | execute` 三态。
- 第二 E 执行前检查 `context.can_execute_action(..., slot=ActionSlot.SKILL)`。
- 单测覆盖 factory、role、combat plan、fallback、中断、第二 E 防抖、输入安全。

`Adler`、`Daphneel`、`Hania` 当前更像初版角色骨架：注册、定位、基本 entry flow 和少量中断测试已经有了，但队伍协作、实机参数校准、planner request/reservation 深度接入还不足。

## 5. 主要问题与优化建议

### 5.1 测试发现规则不稳定

当前测试文件同时存在两套命名：

- 小写：`test_audio_routing.py`、`test_log_gate.py`
- 大写：`TestBaicang.py`、`TestCombatPlanner.py`、`TestNewChars.py`

`pytest --collect-only -q tests` 只收到了 43 个小写 `test_*.py` 用例，未收集大量 `Test*.py` 文件。`run_tests.ps1` 使用：

```powershell
python -m unittest discover -s tests -p "*test*.py" --top-level-directory . -v
```

这在 Windows 大小写不敏感文件系统上可以发现 `Test*.py`，但在大小写敏感环境或直接使用 pytest 时容易漏测。

建议：

1. 在 `pyproject.toml` 中配置 pytest 发现规则：

```toml
[tool.pytest.ini_options]
python_files = ["test_*.py", "Test*.py"]
```

2. 或逐步统一测试文件命名为 `test_*.py`。
3. CI 中明确运行同一套命令，避免本地与 CI 收集范围不同。

### 5.2 全量测试缺少快慢分层

全量 `unittest discover` 本地超时，说明测试集里混有慢测试、硬件相关测试或异步等待测试。比如 `TestMidiPlayer.py` 中存在 `await asyncio.sleep(60)` 的阻塞型测试辅助逻辑。

建议：

- 将纯单元测试、图像识别测试、音频/设备测试、集成慢测拆分。
- 添加 `fast`、`slow`、`integration` 标记。
- 日常开发默认跑 fast。
- PR/Release 再跑 slow/integration。
- 对可能等待真实时间的测试使用 fake clock、短 timeout 或可取消任务。

推荐命令分层：

```powershell
python -m pytest -m "not slow and not integration"
python -m pytest -m "slow or integration"
```

### 5.3 生产代码中写入了未验证机制

`PROJECT_RULES.md` 已明确要求：

- 类 docstring 只包含已确认的实现策略。
- 游戏机制研究放在 `NTE/research/` 或 `docs/`。
- 外部攻略来源标注 `[EXTERNAL]`，不标 `[CONFIRMED-CODE]`。

但 `Adler.py`、`Daphneel.py`、`Hania.py` 的生产代码 docstring 写入了大量外部机制描述。这些内容即使标了 `[EXTERNAL]`，也会让生产代码承担研究记录职责。

建议：

- 把角色机制说明迁移到 `docs/research/<角色名>.md`。
- 生产代码 docstring 只保留：
  - 角色定位。
  - 当前实现策略。
  - 已知限制。
  - 实机校准状态。

### 5.4 长循环中断检查不一致

`Baicang._perform_burst()` 做得较好：有 deadline、切人检查、死亡检查、`check_combat()`、方向键 finally 释放。

但其他新增角色存在不一致：

- `Adler._stack_ye()` 检查 `is_current_char` 和 `is_dead`，但未调用 `check_combat()`。
- `Daphneel._perform_burst()` 检查 `is_current_char` 和 `is_dead`，但未调用 `check_combat()`。

这与项目规则“任何长循环必须分片执行并检查 combat 状态”不完全一致。

建议为所有长循环统一模板：

```python
while self._now() < deadline:
    if not self.is_current_char:
        return
    if self.is_dead:
        return
    self.check_combat()
    ...
```

如果有持续按键，则必须：

```python
try:
    self.task.send_key_down(key)
    ...
finally:
    self.task.send_key_up(key)
```

### 5.5 时间源应改为 monotonic

`PROJECT_RULES.md` 要求生产代码使用 `_now()` 包装 `time.monotonic()`，但新增角色目前仍使用 `time.time()`。

建议统一：

```python
def _now(self):
    return time.monotonic()
```

理由：

- 战斗 deadline 不应受系统时间调整影响。
- fake time 测试仍可覆盖 `_now()`。
- 改动小，收益稳定。

### 5.6 新增辅助角色还没有真正使用队伍协作能力

`Adler`、`Hania` 当前基本是：

- 入场执行 E/Q。
- sleep 一小段。
- 战斗结束后切出。

这只是单角色 entry flow，还没有充分发挥 OKNTE 的 planner 能力。相比之下，已有复杂角色如 `Hotori` 会使用：

- `combat_policies(context)`
- `context.reserve_actions(...)`
- `context.request_route(...)`
- route/window lifetime
- reservation finish callback

建议后续把辅助角色改成真正的队伍轴节点：

- `Hania`：部署 buff 后发布 buff window，请求主 C 回场。
- `Adler`：开盾后可发布保护窗口，避免队友关键技能被提前消耗。
- `Daphneel`：作为主 C 时应能接受 support 的 return-to-source 请求，而不是只靠自身 Q/E 顺序。
- `Baicang`：可作为主 C 标杆，后续围绕它设计 support -> main DPS 的队伍轴。

### 5.7 `Baicang` 的 burst 参数需要实机校准闭环

`Baicang` 当前参数合理，但仍属于默认估计：

- `ULT_FIELD_DURATION = 8.0`
- `DODGE_CLICK_INTERVAL = 0.12`
- `DODGE_SLICE_DURATION = 0.3`
- `SKILL_CHECK_INTERVAL = 1.5`
- `SKILL_READY_STREAK_THRESHOLD = 3`
- `SECOND_SKILL_MODE = "observe"`

建议建立实机校准表：

| 参数 | 当前值 | 需要验证的问题 |
| --- | --- | --- |
| `ULT_FIELD_DURATION` | 8.0 | Q 后有效输出窗口是否正好 8 秒 |
| `DODGE_CLICK_INTERVAL` | 0.12 | 是否漏触发/过密/卡输入 |
| `DODGE_SLICE_DURATION` | 0.3 | 检查频率是否影响输出 |
| `SKILL_CHECK_INTERVAL` | 1.5 | 是否错过第二 E 窗口 |
| `SKILL_READY_STREAK_THRESHOLD` | 3 | 是否能过滤 UI 单帧误判 |
| `SECOND_SKILL_MODE` | observe | 何时切到 execute |

实机验证时应保留日志和录屏，记录游戏版本、分辨率、帧率、队伍、网络/性能状态。

### 5.8 CI 配置可以补质量门禁

当前 `.github/workflows/test.yml` 主要运行 unittest。建议增加：

```powershell
python -m ruff check src tests
python -m ruff format --check src tests
```

考虑到上游已有 AI review workflow，基础 lint/format 更应该作为低成本硬门禁。

同时，`ai_code_review.yml` 的 `PROJECT_CONTEXT` 仍写着 “Wuthering Waves”，与 OKNTE/《异环》不一致。建议改成 Neverness To Everness / OKNTE 的真实上下文，否则 AI review 会带入错误项目背景。

## 6. 角色级审查

### 6.1 Baicang

评价：当前新增角色中最成熟，接近可合并状态。

优点：

- planner action 语义清楚。
- E/Q/fallback 拆分合理。
- fallback 不参与切人评分。
- Q 成功后 burst 内部管理完整。
- 第二 E 保护链谨慎，默认 observe，不贸然输入。
- 测试覆盖充分。

建议：

- `_now()` 改为 `time.monotonic()`。
- `SECOND_SKILL_MODE` 后续可接入角色配置，而不是类常量固定。
- burst 日志可减少热循环输出，只保留状态变化。
- 实机确认第二 E 后再从 observe 切到 execute。

### 6.2 Adler

评价：可作为初版辅助骨架，但还不够 OKNTE 化。

优点：

- 定位为 `SUB_DPS + SETUP_ONLY` 合理。
- 不主动开场，符合项目规则。
- entry flow 清楚：叠业 -> E -> Q。
- 有基础中断测试。

风险：

- `_stack_ye()` 未调用 `check_combat()`。
- “业”层数机制未与 UI/状态绑定，当前只是时间驱动普攻。
- 护盾收益没有转化为 planner 协作请求或窗口。

建议：

- 增加 `check_combat()`。
- 把机制描述移到研究文档。
- 后续用 `combat_policies()` 或 action followup 发布保护窗口。

### 6.3 Daphneel

评价：主 C 骨架成立，但机制依赖高，实机不确定性较大。

优点：

- Q 优先、Q 失败后 E 的 flow 简洁。
- burst 内 skill 最多一次，避免无脑连点。
- 检查了 skill reservation。

风险：

- 弹反充能机制当前只能依赖 `ultimate_available()`，无法感知弹反时机。
- burst 循环未调用 `check_combat()`。
- `click_skill()` 在 burst 中没有短 timeout，可能拖住输出窗口。

建议：

- burst 中加 `check_combat()`。
- burst 内 E 使用短 timeout。
- 后续结合声音驱动/反击触发，建立“弹反成功 -> Q ready -> burst”的更真实链路。

### 6.4 Hania

评价：辅助逻辑太薄，目前只是 Q/E 顺序释放。

优点：

- `SUB_DPS + SETUP_ONLY` 合理。
- Q -> E 顺序清楚。
- Q 失败后仍尝试 E，容错方向正确。

风险：

- buff 窗口没有被 planner 记录。
- 没有请求主 C 回场。
- 与暗属性/队伍构成相关的外部机制尚未落地。

建议：

- E/Q 成功后发布 buff window。
- 使用 `request_switch()` 或 `request_route()` 让主 C 回场。
- 与 `Baicang`、`Daphneel` 建立队伍轴测试。

## 7. 推荐发展路线

### 阶段一：收敛工程质量

目标：让当前分支具备稳定合并基础。

任务：

1. 修复测试发现规则。
2. 拆分快慢测试。
3. 新增 CI ruff check/format。
4. 所有 `_now()` 改为 `time.monotonic()`。
5. 所有长循环补齐 `check_combat()`。
6. 外部机制迁移到 `docs/research/`。

验收：

- 新增角色 fast tests 稳定通过。
- pytest 和 unittest 收集范围一致。
- ruff check/format 通过。
- 生产代码 docstring 不再承载未验证攻略。

### 阶段二：以 Baicang 为主 C 标杆

目标：把 `Baicang` 做成第一个高质量主 C 模板。

任务：

1. 实机校准 dodge interval、burst duration、第二 E 时机。
2. 确认 `SECOND_SKILL_MODE=execute` 是否安全。
3. 加入录屏/日志对照记录。
4. 把参数沉淀为角色配置项或注释明确校准来源。

验收：

- 有至少 3 组不同战斗场景录屏和日志。
- 第二 E 不误触、不漏触或明确保持 observe。
- 战斗结束无方向键残留。

### 阶段三：构建队伍轴

目标：从单角色脚本升级为队伍级战斗策略。

推荐先做：

- `Hania -> Baicang`
- `Adler -> Baicang`
- `Hania -> Daphneel`

任务：

1. support 成功 E/Q 后发布 buff/shield window。
2. 请求主 C 回场。
3. reservation 保护主 C 关键技能。
4. 单测验证切人顺序、失败 fallback、request 生命周期。

验收：

- planner 决策日志能解释为什么切入 support、为什么回主 C。
- support 不会长期占场。
- 主 C 不会被 support 的 request 错误阻断。

### 阶段四：机制感知与触发源融合

目标：把视觉、声音、CD、角色状态结合起来，减少盲打。

方向：

- 利用声音驱动增强闪避/反击。
- 对关键 buff/状态增加视觉识别或日志采样。
- 为高机制角色建立“状态机 + 超时 + fallback”。
- 对无法识别的机制明确降级策略。

验收：

- 状态机每个阶段都有退出条件。
- 关键动作失败后不伪造成功。
- 无实机证据的策略保持保守默认。

## 8. 优先级清单

P0：

- 修复测试发现规则。
- 所有新增长循环补 `check_combat()`。
- `_now()` 改 `time.monotonic()`。
- 明确 fast test 命令。

P1：

- 将 `[EXTERNAL]` 机制文档迁移到 `docs/research/`。
- CI 添加 ruff。
- `Daphneel` burst 内 E 使用短 timeout。
- `Baicang` 参数做实机校准记录。

P2：

- `Hania/Adler` 接入 planner request/reservation。
- 队伍轴单测。
- 角色参数配置化。
- 实机日志回放与调试工具。

## 9. 最终判断

当前项目具备继续推进价值。它已经站在 OKNTE 正确的扩展点上：`CombatPlanner`、角色声明式动作、slot reservation、角色中心识别。短期内不要急着继续横向增加大量角色；更值得做的是把 `Baicang` 打磨成主 C 模板，把 `Hania/Adler` 打磨成 support 模板，再把两者连接成队伍轴。

如果按“一个成熟主 C + 一个成熟辅助 + 一条可测试队伍轴”的路线推进，后续新增角色会快很多，也更容易被上游接受。

## 10. 2026-07-16 双队目标复审

### 10.1 当前基线

- 分支：`feat/baicang-combat`
- 复审提交：`bd95014`
- 工作树在复审开始时干净。
- 聚焦验证：`TestBaicang`、`TestBaicangPlannerIntegration`、`TestNewChars`、
  `TestTeamPlannerSimulation`、`TestCombatPlanner` 共 `191 passed in 3.57s`。
- 当前测试已经验证新角色 action slot、route 强制动作和单角色失败路径，但
  `TestTeamPlannerSimulation` 仍主要是把四个角色分别放进真实 Planner 执行，尚未构成用户目标
  阵容的完整切人时序、窗口和模式测试。

### 10.2 产品目标调整

项目不再以“白藏、达芙蒂尔、阿德勒、哈妮娅四个新增角色都能独立出招”为阶段终点，而以两套
真实可用阵容为产品目标：

1. 白藏失谐队：`白藏 + 达芙蒂尔 + 早雾 + 法蒂娅`；竞速时法蒂娅替换为哈妮娅。
2. 小吱盈蓄队：`小吱 + 九原 + 翳 + 零`。

角色数量不再是进度指标。真正的进度指标是：主 C 有效站场占比、无意义切人次数、关键状态
识别可信度、失败后恢复时间、输入安全和实机连续运行稳定性。

### 10.3 最新架构判断

第一队应作为当前唯一主线。其五个候选角色均已存在内置注册，可以在不引入新框架的情况下，
沿用 `ActionIntent + request_route + request_switch + deadline` 完成最小队伍轴。但早雾和法蒂娅
仍是通用 Q/E 骨架，达芙蒂尔仍按 MAIN_DPS 建模，三者都不符合用户给出的短切、控制和生存职责。

第二队暂列下一里程碑。主要阻塞不是 Planner API，而是机制感知：翳没有内置角色实现，小吱
只在大招循环中用颜色比例粗判一次技能时机，项目也没有明确的盈蓄状态。此时直接写固定四人
轮转会得到“看起来会切人、实际上不懂机制”的自动战斗。

### 10.4 决策优先级

P0：

- 增加最小结构化战斗轨迹，支持录屏与决策对齐。
- 把 fast、integration、hardware 测试分层；禁止把本地全量 pytest 当作默认安全门禁。
- 将“队伍仿真”升级为真实切人、route 生命周期、超时和失败恢复测试。

P1：

- 补强早雾聚怪/控制 action 和法蒂娅 SUPPORT 维护 action。
- 将达芙蒂尔从第二长期主 C 收敛为技能就绪才入场的短切副 C。
- 完成 `早雾 -> [法蒂娅] -> [达芙蒂尔] -> 白藏` 的有期限开场路线。
- 实机校准白藏站场行为，第二 E 继续保持 `observe`。

P2：

- 增加显式首领策略，减少无意义切人并保护白藏连续站场。
- 增加己方生存状态接口；未知状态下法蒂娅采用低频维护，不伪造危险血线响应。
- 增加 `早雾 -> 哈妮娅 -> [达芙蒂尔] -> 白藏` 竞速路线。

P3：

- 实现翳的内置角色、角色中心绑定和独立行为验证。
- 重构小吱的金谷检测与 burst 循环，补 monotonic deadline、中断检查和状态防抖。
- 实机确认九原聚怪、零环合与盈蓄状态之间的真实关系。

P4：

- 完成 `九原 -> 翳 -> [零] -> 小吱` 的有期限铺垫路线。
- 建立盈蓄激活、失效、未知和重建的状态机。
- 完成连续运行、失败恢复和主 C 站场占比验收。

### 10.5 最终路线

后续主方向确定为：**第一队先闭环，第二队后建设；验证优先，route 目标动作自包含，路线有期限，
状态未知就降级。** 近期不开发通用 DSL；永久 reservation 只允许用于类似上游 `Hotori` 的
机制不变量，并具备 route 覆盖和 reset 清理；不把固定攻略顺序直接写成无限循环，也不在缺少
实机证据时宣称血线、金谷或盈蓄已经被可靠识别。

双队的详细状态机、模式差异、实施批次和验收门槛见
`docs/research/team_axis_design.md`。
