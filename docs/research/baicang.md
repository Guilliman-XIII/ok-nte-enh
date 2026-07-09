# 白藏 (Baicang) 游戏机制研究

> 本文档收集外部攻略来源的游戏机制描述，供实现参考。所有内容标注 `[EXTERNAL]`，未经实机验证。

## 基本信息

- 元素：咒系 (RED) [EXTERNAL: 3DM/米游社/豌豆荚]
- 定位：主C (MAIN_DPS)
- 核心机制：闪避(右键)攻击为核心输出

## 技能机制

### 普攻 (E / 技能)
[EXTERNAL: GameKee/3DM]
- 咒系近战攻击
- 释放后进入短暂硬直
- CD 约 6-8 秒（待实机确认）

### 大招 (Q / 终结技)
[EXTERNAL: GameKee/3DM]
- 进入爆发状态，持续约 8 秒（保守估计）
- 5觉后爆发持续时间可能延长至 20 秒 [HYPOTHESIS]
- 爆发期间闪避攻击伤害提升

### 闪避攻击 (右键)
[EXTERNAL: B站攻略视频]
- 白藏核心输出手段
- 闪避后右键触发追击
- 爆发期间伤害倍率提升

## 待验证假设

- [HYPOTHESIS] E-before-Q 或 Q-first（当前实现为 E-first）
- [HYPOTHESIS] 爆发窗口时长（保守 8 秒，5觉后 20 秒）
- [HYPOTHESIS] 方向键持续按住 vs 脉冲
- [HYPOTHESIS] 第二 E 在爆发窗口内是否可用

## 队伍搭配

[EXTERNAL: GameKee/3DM 配队攻略]
```
哈妮娅(Q→E) → 阿德勒(叠业→E→Q) → 达芙蒂尔(弹反→Q→E→爆发) → 白藏(E→Q→闪避输出)
```

## 实机校准项

| 参数 | 当前值 | 需要验证的问题 |
| --- | --- | --- |
| `ULT_FIELD_DURATION` | 8.0 | Q 后有效输出窗口是否正好 8 秒 |
| `DODGE_CLICK_INTERVAL` | 0.12 | 是否漏触发/过密/卡输入 |
| `DODGE_SLICE_DURATION` | 0.3 | 检查频率是否影响输出 |
| `SKILL_CHECK_INTERVAL` | 1.5 | 是否错过第二 E 窗口 |
| `SKILL_READY_STREAK_THRESHOLD` | 3 | 是否能过滤 UI 单帧误判 |
| `SECOND_SKILL_MODE` | observe | 何时切到 execute |
