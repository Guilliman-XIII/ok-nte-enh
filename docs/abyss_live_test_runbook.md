# 双队深渊实机联调手册

> 适用版本：`feat/baicang-combat`，1920×1080 窗口模式，120 FPS。
> 目标：用录屏和 Planner 日志确认真实技能、切人、环合与失败恢复，不以“角色动了”代替验收。

## 1. 测试前检查

1. 启动后先在日志确认存在 `OKNTE runtime version=... commit=... source=...`，记录本轮实际提交号。
2. 在角色中心确认四名角色均识别为对应内置逻辑，尤其是翳应绑定到内置 combo“翳”。
3. 在“队伍管理”扫描当前队伍，保证四个头像均已关联角色特征；严格预设缺少任一头像特征都会拒绝启动。
4. 选择“白藏竞速队”或“小吱盈蓄队”，点击“填入扫描”，核对四个槽位后点击“保存预设”。
5. 进入对应深渊队伍后点击“用于下一场”。状态必须显示“下一场：队名（严格校验）”。
6. 使用默认战斗键位；保持游戏窗口可见且不最小化。
7. 开启现有声音闪避/反击；第一轮不调整声音阈值。
8. 开启屏幕录制，保留游戏声音；不要把录屏、截图或本地日志提交到 Git。
9. 第一轮选“敌人能存活 40 秒以上、队伍不容易暴毙”的中等压力多目标层。过低层看不到小吱
   首轮爆发后的完整环合循环，过高层会把生存问题和轮转问题混在一起。

武装只在四槽校验通过并成功构造角色后消费。出现“队伍预设校验失败”时，自动战斗不会降级使用上次
队伍或通用脚本，武装状态会保留；修正阵容/特征后可再次触发检测。切换第二队时必须选择并武装第二
队预设，不能只在游戏内换队。

旧的手动“固定队伍”入口仍可用于日常兼容，但它不提供深渊严格校验，不作为双队验收入口。

## 2. 第一队：白藏竞速队

阵容成员：`白藏 + 达芙蒂尔 + 早雾 + 哈妮娅`。槽位按游戏中的实际顺序保存，不为文档顺序重排。

预期首轮日志顺序：

```text
strict route locked: Baicang abyss opener
Sakiri_skill
Hania_ultimate                 # 无能量时允许跳过
Hania_skill
Daphneel_skill
Daphneel_ultimate              # 无能量时允许跳过
strict route fulfilled: Baicang abyss opener
switch request: return Baicang after Daphneel burst
```

验收观察：

- 早雾首先聚怪，哈妮娅和达芙蒂尔不长时间占场。
- 达芙蒂尔 E 后若 Q 可用，应进入有界爆发，再回白藏。
- 白藏 Q 后保持普通攻击输出；声音模块继续负责闪避/反击。
- 哈妮娅 Q 不可用时路线继续，不在哈妮娅处等待。
- 任一辅助 E/Q 点击失败时应出现 optional step skip，并继续回白藏，不能重复空放到超时。
- 后续普通短切结束后，即使白藏 E/Q 仍在冷却，也应看到 `return Baicang after ...`。
- 24 秒后仍未完成时应出现 route deadline 日志并恢复普通 Planner。

## 3. 第二队：小吱盈蓄队

实际槽位：`小吱 + 零 + 九原 + 翳（狼叔）`。Planner 按角色类型协作，但严格预设会记录并核对当前槽位顺序。

预期关键顺序：

```text
Jiuyuan_skill
Zero_ultimate                  # 无能量时允许跳过
Zero_skill
return Chiz                    # 不在零场上等待第二次 E
Chiz_ultimate
Chiz_skill_chain               # 最多三次 E；非大招期每段前两次平 A
strict route completed entry reaction Chiz -> Jiuyuan
Jiuyuan_ultimate               # 不可用时允许跳过
[Zero_ultimate]                # 不可用时允许跳过
Zero_skill
strict route completed entry reaction Zero -> Yi
Yi_ultimate                    # 无能量时允许跳过
Yi_skill
[Jiuyuan_skill]                # 可用时重新聚怪
return Chiz
strict route fulfilled: Chiz Yingxu abyss cycle
```

验收观察：

- 首轮零 E 后应立即回小吱；零从成功 E 到离场不应继续平 A 超过约 3 秒（不计 Q 动画）。
- 小吱应先完成 Q、最多三次 E 和持续站场，再以 `小吱 -> 九原` 触发第一次创生环合。
- 九原短切后由零 E 铺垫并以 `零 -> 翳` 触发第二次延滞环合。
- 翳完成 Q/E 后立即让出场地，经可选九原 E 聚怪后回小吱。
- 小吱每轮最多自动尝试三次 E；换人、死亡、脱战或技能不可用时立刻停止技能链。
- 小吱大招期间继续按金谷颜色判断 E 时机；非大招期使用“两次平 A -> 一次 E”的保守规则，
  不允许连续猛点 E。
- strict route 等待环合入场时必须执行可被声音模块打断的 0.15 秒短平 A；不得高频重复 Q/R。
- 通用 R 仅在角色切入时尝试一次；同一角色持续站场时，两次 R 至少间隔 20 秒。
- 每次 `Sound action` 触发后都应看到实际 `Executing dodge/counter attack`；出现
  `Sound action discarded after timeout` 即判为失败。
- 35 秒后仍未完成时路线必须解锁，不能继续强制等待。
- 不应再出现零 Q/E 每秒大量重复尝试，或 `strict route waiting while keeping Zero on field` 连续五次以上。

## 4. 首轮回传材料

每队先测一场，只需要保留：

- 从进入战斗前 3 秒到首轮主 C 爆发结束的录屏。
- 对应时间段日志中包含 `strict route`、`planner action`、`planner switch` 的片段。
- 四个主观结果：是否成功聚怪、是否出现错误切人、是否触发目标环合、是否有生存压力。

第一轮不追求通关时间。先确认动作语义和顺序，再根据证据调整动画等待、route deadline、角色
站场和金谷阈值；验证通过后再上高层/Boss 做满奖励冲刺。

测试结束后可直接生成摘要：

```powershell
.\.venv\Scripts\python.exe -m src.combat.AbyssLogAnalyzer logs\ok-script.log
```

摘要只读取本地日志，列出每次 opener/cycle 的状态、动作、真实环合、切人、可选步骤跳过和声音
接管次数。它不修改配置，也不替代录屏中的技能与 HUD 验证。

## 5. 当前已知限制

- 当前通用自动战斗无法可靠判断“这场是否深渊”，因此严格边界由“用于下一场”显式触发；未武装时
  不会宣称已启用深渊保护。
- 运行层尚未接入按四人集合自动选择预设；本期先采用手动一键武装，避免模糊识别选错队伍。
- 自定义角色数据库首次从 schema v5 升级到 v6 前，会保留
  `custom_chars/db.json.schema-v5.bak`。v6 数据不支持再用旧版 OKNTE 保存。
- 白藏队当前是哈妮娅竞速版，没有按血线自动切法蒂娅。
- 白藏首版采用稳定平 A，不启用尚未实机验证的 Shift 移动攻击；白藏队首轮后由通用 Planner
  调度。小吱队首轮快速回主 C，随后由小吱站场触发双环合循环。
- 攻略资料只用于提出待验证假设。实现依据仍以游戏实机、OKNTE 日志和用户录屏为准。
- 自动化存在游戏账号处罚风险；继续沿用 OKNTE README 的风险边界，不进行注入或内存读取。

## 6. 2026-07-18 最新硬验收门槛

下一轮录像和日志必须同时满足：

1. 九原 E 成功发送后至少等待 1.2 秒再切人；录像中聚怪动作应完成，日志不得在同一秒内立刻
   出现 `Jiuyuan -> Zero`。
2. 小吱队 strict route 完成后必须直接回小吱；若小吱切人冷却未结束，只能原地短暂等待，
   不得被普通元素环合改切第三人。真实切回后应出现 `return request fulfilled`，同一请求不得
   再次阻塞小吱动作。
3. 小吱每次金谷颜色判定通过只允许一个物理 E 按键；一次大招最多三次，接受的两次 E 之间
   至少间隔 0.6 秒。日志应包含 `ultimate skill gate accepted`，不应再出现单个逻辑 E 内的
   连续按键风暴。
4. 目标两队的 R 必须严格限定：白藏和达芙蒂尔允许，早雾、哈妮娅、小吱、零、九原、翳均不得
   出现 `default_arc`。
5. 哈妮娅或达芙蒂尔 E 点击失败后，4 秒内不得因同一技能再次吸引 Planner 切入。
6. 任一 `Sound action` 都必须对应实际 `Executing dodge/counter attack`；出现一次
   `Sound action discarded after timeout` 即判失败。

小吱队若再出现一轮超过 10 次的短时连续切换、回到小吱后不执行主 C 动作，或单次大招实际
发送超过三个 E，本轮直接判定 No-Go，不再通过增加延时继续调参。

## 7. 小吱等待期技能修复后的单场复测

本轮只需测试小吱队一场完整战斗，优先选择能持续施压但不会开场秒杀主 C 的深渊层。队伍槽位
保持：1 号小吱、2 号零、3 号九原、4 号翳。开始前在队伍管理选择“小吱盈蓄队”并点击
“用于下一场”，不需要重新扫描队伍。

通过条件：

1. 小吱 Q 后等待创生时，日志应出现 `planner action Chiz -> Chiz_skill_chain`；E 不可用时才允许
   出现 `wait_for_strict_route_action`。
2. `Chiz_skill_chain` 不得让 strict route 提前完成；仍须由真实 `Chiz -> Jiuyuan` 入场反应
   推进创生步骤。
3. 小吱必须存活到第一次切九原，并在后续回场继续作为主 C；头像变灰、自动切零或
   `Chiz:mark dead` 任一出现即判失败。
4. 不得出现连续 10 秒尝试切回死亡/不可用角色，或主 C 死亡后辅助之间高频乱切。
5. 每个声音提示必须实际执行；出现 `Sound action discarded after timeout` 即判失败。

本轮不需要再录白藏队。录像保留完整战斗，分析时重点看小吱首次 Q 后到第一次切九原，以及死亡
或通关前最后 25 秒。
