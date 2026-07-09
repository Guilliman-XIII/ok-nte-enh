# AGENTS.md

## 适用范围

本文件适用于整个仓库。除非用户或更深层目录中的 `AGENTS.md` 明确覆盖，所有智能体修改、审查、重构、测试和文档工作都应遵守本文。

## 项目定位

`ok-nte` 是一款基于 `ok-script` 的 Windows 桌面自动化工具，面向《异环》提供 UI 图像识别、OCR、OpenVINO 目标检测、WASAPI 进程音频捕获、模拟键鼠、自动战斗、日常任务、小游戏和角色中心等能力。

项目默认原则是通过用户可见的界面和系统输出信号与游戏交互：截图、OCR、图像特征、声音反馈和普通输入事件。

## 不可破坏的约束

- 不提交用户本地日志、截图、抓包样本、账号信息、个人路径、配置密钥或任何可能识别用户环境的数据。
- 不改变 README 与 `src/config.py` 中“仅通过 UI/系统输出交互”的安全边界，除非用户明确要求并同步更新风险说明。
- 不把长耗时模型加载、音频循环、路径循环、OCR 大扫描或文件 I/O 放进 UI 渲染热路径。
- 不为了小范围功能引入大型框架、服务端组件或异步运行时。

## 架构边界

- `main.py` / `main_debug.py`：启动入口。只负责加载配置并启动应用，不放业务逻辑。
- `src/config.py`：ok-script 配置、全局配置项、任务注册、窗口/截图/OCR/模板配置。新增任务、标签页或全局设置必须在这里保持默认值和说明。
- `src/tasks/`：一次性任务和业务流程，例如日常、钓鱼、异象、音游、咖啡、粉爪大劫案等。任务应通过 `BaseNTETask` 和 mixin 使用公共能力。
- `src/tasks/trigger/`：常驻触发任务，例如自动战斗、声音触发、跳过对话、快速传送、登录、粉爪便利功能。触发循环必须轻量、可中断，避免阻塞 executor。
- `src/tasks/mixin/`：跨任务复用能力。把通用视觉、移动、角色 UI、窗口/配置辅助放在这里，不要把某个任务的私有规则扩散进 mixin。
- `src/combat/`：自动战斗检测、角色动作执行、战斗 planner 接入。这里的改动影响面大，必须保守并补测试。
- `src/combat/planner/`：角色协作、动作意图、切人策略和请求生命周期。保持公开 API 简洁，角色代码不要依赖以下划线开头的内部字段。
- `src/char/`：内置角色逻辑和 `BaseChar`。角色动作应声明意图、调用既有动作 helper，避免直接操纵 planner 内部状态。
- `src/char/custom/`：自定义角色、出招表、特征管理和内置 combo 映射。保持数据兼容，避免破坏已有用户配置。
- `src/ui/`：PySide6/qfluentwidgets UI 标签页和管理界面。UI 代码只做展示、轻量状态协调和用户输入，不承载重业务。
- `src/sound_trigger/`：声音驱动闪避/反击与 WASAPI 进程音频捕获。保持捕获为系统音频层读取，不要改为进程注入或 Hook。
- `src/interaction/`：Windows 窗口与输入交互。平台 API 调用要保持最小化，涉及前后台输入时要考虑用户鼠标干扰和窗口状态。
- `src/scene/`：场景状态和屏幕位置抽象。场景状态应是高层缓存，不要塞入任务私有状态。
- `src/coffee/`、`src/midi_player/`、`src/heist_path/`：领域子系统。优先在子系统内部修复和测试，避免把细节泄漏到基础任务层。
- `assets/`、`icons/`、`ok_templates/`、`mid_lib/`：运行资源、模板、图标、MIDI。避免无意义大文件；更新模板要说明来源和适配范围。
- `i18n/`：gettext 翻译文件。新增用户可见字符串时检查是否需要同步 `.po`，编译 `.mo` 时不要手工篡改生成文件。
- `tests/`：unittest 测试。新增共享逻辑、planner、解析/转换、声音捕获、数据迁移时应补对应测试。
- `docs/`：开发文档。修改 planner 或角色协作 API 时，同步检查 `docs/combat_planner.md`。

## 开发流程

修改前先判定影响范围：任务流程、自动战斗、角色逻辑、planner、声音触发、UI、i18n、资源、配置或文档。保持 diff 小而可审查，避免顺手重构无关文件。

推荐验证命令：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "*.py"
```

针对单个测试文件：

```powershell
.\.venv\Scripts\python.exe -m unittest tests.TestCombatPlanner
.\.venv\Scripts\python.exe -m unittest tests.test_sound_trigger_capture
```

仓库提供的逐文件测试脚本：

```powershell
.\run_tests.ps1
```

语法快速检查：

```powershell
.\.venv\Scripts\python.exe -m py_compile path\to\file.py
```

如果环境中安装了 ruff，可运行：

```powershell
ruff check .
```

不要假设所有开发依赖都已安装；如果无法运行某个命令，在最终回复中说明原因。

Python 命令应优先使用仓库虚拟环境。Codex 在本仓库中应直接调用 `.venv` 解释器，避免通过 `$py` 和 `&` 包装 Python 命令；该写法在沙箱下可能导致 `py_compile` 写入 `__pycache__` 时出现权限错误。

```powershell
.\.venv\Scripts\python.exe -m py_compile path\to\file.py
```

存在 `.venv` 时不要直接调用全局 `python`、`pip` 或 `pytest`；使用 `.\.venv\Scripts\python.exe`、`.\.venv\Scripts\python.exe -m pip`、`.\.venv\Scripts\python.exe -m pytest`。

## Python 规范

- 目标 Python 版本为 3.12+。
- 遵循 `pyproject.toml` 中的 ruff 设置：行宽 100、双引号、导入排序。
- 优先使用项目已有 helper、mixin 和 ok-script API，不要为局部需求绕过框架。
- 保持类型表达清晰。复杂数据优先使用 `dataclass`、枚举或明确结构，而不是松散字典。
- 构造函数应追求简洁、优雅和低复杂度；但不要仅为降低单函数长度而把本可直读的初始化逻辑拆成多个私有函数。
- 生产代码避免裸 `except` 和静默失败；捕获异常时记录足够上下文，并保持任务可恢复或明确中止。
- 不在循环中频繁创建重模型、重模板或大数组；需要缓存时使用已有缓存模式和清理路径。
- 线程、事件和后台循环必须有停止条件，避免退出后仍持有音频、输入或模型资源。
- 日志不要包含用户账号、完整本机路径、隐私截图内容或可识别用户环境的信息。

## 自动化与安全边界

- 默认交互方式是截图识别、OCR、WASAPI 音频、窗口 API 和普通键鼠输入。
- 输入节奏要保守，避免不可中断的高频点击、长时间按键或在错误窗口中持续输入。
- 涉及前台窗口、后台截图、鼠标位置和键盘布局时，兼顾 README 中的用户注意事项。
- 声音触发用于听取游戏输出音频，不应演变为进程注入、音频 API Hook 或内存读取。
- 若新增风险更高的实验能力，必须默认关闭，文案说明风险，且保留现有 UI/声音方案作为默认路径。

## 视觉、OCR 与 OpenVINO

- 坐标优先使用相对屏幕比例和 `box_of_screen`，不要硬编码单一分辨率像素，除非已有上下文证明安全。
- 支持范围是 16:9、1920x1080 或更高；新增识别逻辑要考虑 1080p、1440p、2160p。
- 图像预处理优先放在 `src/utils/game_filters.py` 或 `src/utils/image_utils.py`，避免各任务复制粘贴。
- OpenVINO 检测应复用 `BaseNTETask.openvino_detect()` 和全局模型状态，避免并发清理或重复初始化导致卡顿。
- OCR 区域尽量收窄，匹配规则要容忍中英文 UI、简繁转换和常见 OCR 误识别。
- 模板或特征资源更新后，检查 `Labels`、`assets/coco_annotations.json`、`ok_templates/` 和相关测试/文档是否需要同步。

## 战斗与角色 Planner

- `AutoCombatTask` 只应协调战斗循环；角色动作和 planner 策略放在 `BaseCombatTask`、`BaseChar` 或 `src/combat/planner/`。
- `CombatCheck` 的战斗状态检测影响所有自动战斗入口。调整入战/脱战、boss、目标、Lv、血条、uncertain 状态时必须补测试或说明人工验证。
- 角色实现优先覆盖 `describe_role()`、`combat_intents()`、`combat_policies()` 和小型动作 helper。
- `combat_intents()` 必须保持声明式，不要在评分扫描中发送输入、切人、点击或发布副作用请求。
- 协作请求应通过 planner 公开 API 表达，不读取或修改 `CombatContext` 内部字段。
- 修改 planner 公开 API 时同步更新 `docs/combat_planner.md` 和 `tests/TestCombatPlanner.py`。
- 角色死亡、切人失败、动画过长、终结技点击失败等路径要保持可恢复或抛出既有异常，不要无限循环。

## 任务与触发循环

- 一次性任务应继承或复用 `BaseNTETask` / `NTEOneTimeTask`，把可重复动作拆成小方法，便于恢复和测试。
- 触发任务 `trigger_interval` 不要过低，除非工作量极小且已有节流。
- 任务运行前检查场景、队伍、窗口、配置等前置条件；失败时给出可理解日志。
- 对路线脚本和长流程任务，优先维护清晰状态机和中断点，不要用不可控的长 `sleep` 掩盖识别问题。
- 对咖啡、音游、粉爪等子系统，优先在本子系统内添加纯逻辑测试。

## UI 与 i18n

- UI 文案保持简洁，配置项要有默认值和 `config_description`。
- 不要在 UI 线程执行长耗时 OCR、模型推理、音频捕获或文件扫描。
- UI 结构尽量复用现有 qfluentwidgets/ok-script 模式，不引入新的 UI 框架。
- 对角色中心、自定义出招表、特征管理等数据编辑 UI，保存前做校验，保持旧数据可读。

## 声音触发

- `src/sound_trigger/capture/` 负责音频源抽象、进程解析和 WASAPI loopback。Windows 结构体布局和 HRESULT 格式有测试，修改时先看 `tests/test_sound_trigger_capture.py`。
- 音频线程失败后应可重启或清晰停止；不要让异常静默杀死声音触发。
- 音频阈值、采样率、模板文件路径变化要保持配置兼容。
- 没有样本文件时应快速失败，避免运行期表现为无响应。

## 资源、配置与数据兼容

- `configs/`、用户截图、日志和本地生成数据不应提交。
- 自定义角色和特征数据要保持向后兼容；新增字段需要默认值或迁移逻辑。
- 资源文件名和路径要跨 Windows 大小写/分隔符保持稳定。
- 大型模型、图片、音频、MIDI 或生成物进入仓库前要确认必要性。
- 不要改动 `LICENSE`、免责声明、赞助链接或发布配置，除非用户明确要求。

## 测试策略

- planner、纯逻辑解析、数据迁移、配置转换、声音捕获辅助函数应优先写 unittest。
- 测试应服务风险控制，不要为普通 UI 拼装、简单构造函数、直观胶水代码或低风险改动机械增加测试。
- 图像识别或 UI 自动化难以完全单测时，至少隔离纯计算部分，并在最终回复说明人工验证范围。
- 修复 bug 时尽量添加回归测试，尤其是角色协作、战斗脱出、声音触发重启、OCR 解析和自定义角色数据。
- 不依赖真实游戏窗口的测试应保持可在 CI/普通开发机上运行。
- 需要 Windows 或真实音频/截图环境的测试应使用 `skipUnless` 或明确说明。

## 最终回复要求

完成改动后，最终回复应简要说明：

- 改了哪些文件。
- 运行了哪些验证命令。
- 哪些验证未运行以及原因。
- 如果改动涉及自动化安全边界、声音捕获、战斗状态或用户数据，说明风险和默认行为。

## 战斗角色开发规则

> 以下规则适用于所有角色自动化实现。优先级从高到低不可逾越。

### 核心优先级

```
1. 稳定 — 不崩、不卡、不残留按键、不伪造状态
2. 高效自动化 — 最大化有效输出时间，最小化人工干预
3. 简洁 — 用最少的代码表达完整逻辑，但不牺牲稳定性
4. 美观 — 代码可读、日志清晰、结构整洁
```

当两个原则冲突时，高优先级原则胜出。例如：不能为了"高效"而省略异常检查（稳定 > 高效）；不能为了"简洁"而省略必要的中间变量（简洁不影响稳定性时才追求）。

### 稳定

- 所有 `send_key_down` 必须有对应的 `send_key_up`，且放在 `try/finally` 的 `finally` 块中。
- 禁止在 `except` 中吞掉 `NotInCombatException`、`TaskDisabledException`、`CharDeadException` 或项目既有的中断异常。
- 任何长循环（>0.5 秒）必须分片执行，每个分片后检查：`is_current_char`、`is_dead`、`check_combat()`、`deadline`。
- 动作返回值必须真实反映执行结果。`True` 表示实际执行了有效输入；失败、被拦截、角色不可用时返回 `False`。
- 禁止用兜底动作的执行来伪造主动作的成功。
- 一个 `ActionIntent` 的 `slot` 必须真实反映它消耗的资源。禁止在 `slot=ULTIMATE` 的 action 内部直接调用 `click_skill()`，绕过 planner 对 SKILL 的 reservation 检查。
- 需要在 action 内部执行其他 slot 的技能时，必须通过 `context.can_execute_action(self, slot=...)` 检查 reservation。
- 所有长循环必须有明确的 `deadline`，禁止 `while True`。
- `click_skill()` 默认超时为 15 秒，爆发窗口内必须使用短超时（建议 2 秒）。

### 高效自动化

- 闪避循环中方向键应尽量持续按住，避免每个分片反复按下/释放造成死时间。
- 方向键策略（方向、持续 vs 脉冲）属于实机校准项，不可在缺少实机数据时固化。
- 使用 `self.click(interval=X, key="right")` 而非 `self.click(key="right") + self.sleep(X)`。
- `describe_role()` 必须正确设置 `role`、`field_preference`、`max_field_time`。
- `combat_start_priority` 默认为 0（不主动开场）。
- `MAIN_DPS` 不等于开场角色，开场由 `combat_start_priority` 单独决定。
- Q/E 均不可用或失败时，使用有限时长的闪避攻击兜底，而非普通平A。
- 兜底动作的 `priority_ready` 必须为 `False`，不吸引切人评分。
- E 动作失败后必须 yield fallback_dodge，不能直接 return。

### 简洁

- 每个角色类应有一个 `combat_plan()` 方法和若干私有 helper。
- helper 方法职责单一：`_dodge_attack` 管理完整闪避（含方向键），`_right_click_burst` 只管右键（不含方向键）。
- 避免不必要的 `__init__` 重写，除非有实例状态需要初始化。
- 常量集中定义在类顶部，用注释分组。
- 动作名使用 `角色名_动作` 格式：`baicang_burst_cycle`、`baicang_first_skill`。
- 日志前缀统一为 `[角色名]`。
- 第二 E 使用字符串三态：`SECOND_SKILL_MODE = "observe"`（`disabled | observe | execute`）。

### 美观

- 每个关键步骤有 `self.logger.info(f"{_LOG_PREFIX} ...")` 日志。
- 日志应能从录屏中对照确认执行流程。
- 避免在热循环中打印过多日志（每分片最多 1 条）。
- 类 docstring 只包含已确认的实现策略，不写入未验证的游戏机制。
- 游戏机制研究放在 `docs/research/`，不放在生产代码注释中。
- 外部攻略来源标注 `[EXTERNAL]`，不标 `[CONFIRMED-CODE]`。
- 遵守上游 Ruff 配置：行宽 100、双引号、isort。提交前运行 `ruff format` 和 `ruff check`。

### 测试规范

1. Factory 测试：角色注册、cls、cn_name、element
2. Role 测试：describe_role 返回值
3. CombatPlan 测试：动作优先级、entry flow 顺序、can_execute、priority_ready
4. 状态机测试：第二 E 保护链各阶段、循环中断
5. 输入安全测试：方向键释放、异常传播、零时长
6. Planner 集成测试：通过真实 `CombatPlanner.perform_current_char()` 验证 action history、reservation、strict route

- Mock 不应掩盖真实行为。`TestableBaicang` 的 mock 只覆盖输入方法，不覆盖决策逻辑。
- fake time 不应重复推进：mock 分支推进时间，调用 super 时不推进。
- 方向键次数断言应精确，不用 `>= 1`。
- 每个修复项必须有对应的失败测试。
- 生产代码使用 `_now()` 方法包装 `time.monotonic()`。测试只 patch `_now()`。

### 角色开发模板

1. 调研：确认元素、定位、核心机制（来源标注 `[EXTERNAL]`）
2. 注册：CharFactory 添加 `char_xxx` 条目
3. Role：设置 `describe_role()`
4. CombatPlan：定义动作和 entry flow
5. 输入安全：`_dodge_attack` / `_right_click_burst` / 方向键 try/finally
6. 第二技能保护链（如适用）：CD 确认 → streak → once guard → observe/execute
7. 测试：6 个层次全覆盖
8. Ruff + pytest 全量验证
