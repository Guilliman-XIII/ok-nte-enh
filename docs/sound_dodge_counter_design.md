# 声音闪避 / 反击设计

> 持久设计文档。讲清楚 `src/sound_trigger/` 这套"听声闪避/反击"的工作原理、刻意做出的设计决策，
> 以及改这块代码时不能碰坏的东西。当前状态快照见最新的 `docs/qwen_dual_abyss_handoff_*.md`。

## 0. 第一原则（改任何代码前先读这条）

**闪避是命根子，反击只是锦上添花。** 用户明确：角色基本被打三下就死，所以**任何改动都不得降低闪避可靠性**。
反击（打敌人蓄力破绽）能打得更快，但它是添头，为了它牺牲闪避是本末倒置。下面所有设计都服从这条。

## 1. 它怎么"听"——模板匹配，不是听懂

听觉通道是**纯模板匹配**，不理解游戏机制，只会问"这段声音更像 A 还是更像 B"：

- 两段参考录音：`assets/sounds/dodge.wav`（敌人要动手打你的声音）、`assets/sounds/counter.wav`
  （敌人进蓄力、露破绽的声音）。区分蓄力和攻击的"智慧"**全在这两个 wav 选得准不准上**。
- `SoundListener` 每 `detection_interval=0.025s` 截最近 `sample_len=0.2s` 的游戏声音（WASAPI 进程环回，
  只读系统音频层，不注入不 Hook——见 `AGENTS.md` 安全边界）。
- 实时声音和两段样本都先过 4 阶 Butterworth 高通滤波（截止 1000Hz，砍掉低频轰鸣只留清脆音效），
  再按标准差归一化，然后算**归一化互相关**（`scipy.correlate` FFT），取峰值当相似度。
- 判定：`dodge_score > 0.13` → 闪避；否则 `counter_score > 0.12` → 反击。**闪避音永远先判**（§3）。

绝区零一条龙的听觉通道和本系统是同一师门（都是归一化互相关模板匹配），人家只是在耳朵之上又加了只
"眼睛"（闪光分类器，见 `docs/research/zzz_onedragon_reference.md`）。

## 2. 触发链路

```
SoundListener._check_triggers（每 0.025s 算分）
  → on_dodge_triggered / on_counter_triggered
  → SoundCombatContext._queue_action（排队 + 发抢占信号 _combat_interrupt）
  → 主战斗循环在 sleep_check 里响应，调 execute_pending_action
  → DodgeCounterTrigger.execute_dodge / execute_counter_attack（真正发输入）
```

- 闪避动作 = 快速点按 lshift（`send_key_down("d")` + 点按 lshift + 松开，`DodgeCounterTrigger._default_dodge_action`），
  **不是长按**——长按 lshift+方向是冲刺疾跑（白藏翻滚攻击就是这么踩坑的）。
- 反击动作 = 一次普攻点击（`_default_counter_action`）。
- 抢占机制：声音动作可打断主输出循环（`SoundCombatContext.enter_priority`），但 `in_animation` 时不响应
  （`can_sound_trigger`：`_in_combat and not in_animation`），避免在放技能硬直里乱动。

## 3. 刻意的设计决策

### 3.1 唯一的间隔闸在 DodgeCounterTrigger（双闸已拆）

**坑**：`SoundListener` 内部原本自带一道共享 0.5s 闸（`_trigger_interval=0.5` + `is_allow_successive_trigger=False`），
而且闪避和反击**共用一个 `_last_trigger_time`**。后果有二：

1. 间隔 < 0.5s 的第二次攻击声会在音频层被**静默吞掉**（不打日志、不闪避），角色就这么挨打，查日志还查不到。
2. 闪避音一响就占满 0.5s 窗口，反击音到了也触发不了（互相饿死）。

**修法**：`SoundCombatContext.setup` 创建 `SoundListener` 时传 `is_allow_successive_trigger=True`，废掉这道
监听层闸。唯一的间隔闸下沉到 `DodgeCounterTrigger`，且闪避/反击**各管各的**：
`_min_dodge_interval=0.3s`、`_min_counter_interval=1.0s`。

**为什么闪避是 0.3s**（数据驱动）：日志实测真攻击可 0.343s 连发（旧 0.5s 下限把这次闪避跳了导致挨打），
成功闪避最快间隔 0.509s、中位 11s。取 0.3s 接得住快连招，又比真实闪避节奏宽松，偶尔多闪一下回声（耗体力）
可接受，远好过漏闪。

> ⚠️ 别再往 `SoundListener` 里加回共享间隔闸。去重由 `DodgeCounterTrigger` 的 0.3s 负责。
> （一条龙是触发后 `clear_audio()` 清缓冲去重；本系统靠间隔闸去重，未清缓冲——功能等价，别混改。）

### 3.2 反击默认开，但闪避优先级不变

**坑**：配置项 `Dodge All Attacks` 默认曾是 `True`，它把反击音（`on_counter_triggered`）半路改判成闪避
（`SoundCombatContext._on_counter_triggered`：`"dodge" if self._dodge_all_attacks else "counter"`），
脚本因此从不 punish 敌人蓄力。

**修法**：`config.py` 里 `Dodge All Attacks` 默认改 `False`（`SoundTriggerTask`/`BaseCombatTask` 两处
`.get(..., False)` 兜底同步）。现在敌人冒红光蓄力时脚本会普攻一下打那个"嘣"的脆响。

**为什么不影响闪避**：`_check_triggers` 里**闪避音先判**，真有攻击打过来一定先走闪避，轮不到反击；
执行层闪避/反击虽共用 `_execute_lock`，但反击动作极短（一次点击）且有 1.0s 间隔，挤占窗口可忽略。
若哪天发现反击干扰了闪避，**回退反击（`Dodge All Attacks=True`），保闪避**。

## 4. 视觉闪避：已研究，搁置待命

我们只有"一只耳朵"，一条龙有"耳+眼"，这是它闪避成功率明显更高的根源。视觉方案已研究（详见交接文档 §2.4
与 `docs/research/zzz_onedragon_reference.md`）：

- 已证实敌人受击前 ~0.4-0.5s 冒纯红光（R>170,G<110,B<110），但**全屏红色底噪随场景差异巨大**，绝对阈值不可靠。
- 落地路线：聚焦现有 YOLO 敌框（`CombatCheck.find_target` 战斗时持续在跑，读 `latest_results` 拿框，不用新模型）
  + **相对自身基线突变**（滚动基线，突然飙过数倍且连续两帧）+ 与听觉**取或**，触发后清音频缓冲去重。
- **先离线回放**（用现有录像+抽帧管线算误报/漏报）拿数据，再决定是否上真机。
- 一条龙的"眼睛"是训出来的 YOLOv8n 闪光分类器，数据集绝区零专用不可迁移；训分类器是数据工程，用户已决定搁置。

> 注意：敌人"蓄力红光"（持续亮、该打）和"攻击预警红光"（一闪而过、该闪）是**两种含义相反的红灯**，
> 靠持续时长可分（短闪=闪避、持续=反击窗口）。未来做视觉通道时必须区分这两种，不能见红就闪。

## 5. 改这块代码的清单

- 闪避优先级不可破：`_check_triggers` 闪避先判、`DodgeCounterTrigger` 闪避闸不被反击拖慢。
- 间隔闸只在 `DodgeCounterTrigger`（0.3s/1.0s），别在 `SoundListener` 加回共享闸。
- 音频捕获保持系统音频层读取，不注入不 Hook（`AGENTS.md`）。
- 阈值/采样率/模板路径改动保持配置兼容（`Sound Trigger Config`）。
- 改完跑 `./.venv/Scripts/python.exe -m unittest tests.TestSoundTriggerWiring tests.TestCombatSoundIntegration -v`。
