# 双队深渊实机联调手册

> 适用版本：`feat/baicang-combat`，1920×1080 窗口模式，120 FPS。
> 目标：用录屏和 Planner 日志确认真实技能、切人、环合与失败恢复，不以“角色动了”代替验收。

## 1. 测试前检查

1. 在角色中心确认四名角色均识别为对应内置逻辑，尤其是翳应绑定到内置 combo“翳”。
2. 使用默认战斗键位；保持游戏窗口可见且不最小化。
3. 开启现有声音闪避/反击；第一轮不调整声音阈值。
4. 开启屏幕录制，保留游戏声音；不要把录屏、截图或本地日志提交到 Git。
5. 第一轮选“敌人能存活 40 秒以上、队伍不容易暴毙”的中等压力多目标层。过低层会在第二次零 E
   前结束，过高层会把生存问题和轮转问题混在一起。

## 2. 第一队：白藏竞速队

阵容：`早雾 + 哈妮娅 + 达芙蒂尔 + 白藏`。

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
- 白藏 Q 后保持右键输出；声音闪避/反击仍能工作。
- 哈妮娅 Q 不可用时路线继续，不在哈妮娅处等待。
- 任一辅助 E/Q 点击失败时应出现 optional step skip，并继续回白藏，不能重复空放到超时。
- 后续普通短切结束后，即使白藏 E/Q 仍在冷却，也应看到 `return Baicang after ...`。
- 20 秒后仍未完成时应出现 route deadline 日志并恢复普通 Planner。

## 3. 第二队：小吱盈蓄队

阵容：`九原 + 零 + 翳 + 小吱`，角色栏顺序不要求固定。

预期关键顺序：

```text
Jiuyuan_skill
Zero_ultimate                  # 无能量时允许跳过
Zero_skill
strict route completed entry reaction Zero -> Jiuyuan
Jiuyuan_ultimate               # 不可用时允许跳过
Zero_skill                     # 第二次，可能需要等待冷却
strict route completed entry reaction Zero -> Yi
Yi_ultimate                    # 无能量时允许跳过
Yi_skill
Chiz_ultimate
strict route fulfilled: Chiz Yingxu abyss opener
```

验收观察：

- 第一次零 E 后必须环合切九原，第二次零 E 后必须环合切翳。
- 等第二次零 E 时可以短暂普攻，但不能高速乱切或永久卡住。
- 翳完成 Q/E 后立即让出场地；小吱应以 Q 接管并进入爆发。
- 小吱大招窗口最多自动尝试一次 E；换人、死亡或脱战时立刻退出循环。
- 35 秒后仍未完成时路线必须解锁，不能继续强制等待。
- 小吱完整爆发后应出现 `strict route locked: Chiz Yingxu abyss cycle`，并重复两次零 E 的环合轴；
  后续循环不再强制九原先开场聚怪。

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

- 白藏队当前是哈妮娅竞速版，没有按血线自动切法蒂娅。
- 白藏队首轮后由通用 Planner 调度；小吱队会在每次完整 Q 爆发后自动重建双环合轴。
- 攻略资料只用于提出待验证假设。实现依据仍以游戏实机、OKNTE 日志和用户录屏为准。
- 自动化存在游戏账号处罚风险；继续沿用 OKNTE README 的风险边界，不进行注入或内存读取。
