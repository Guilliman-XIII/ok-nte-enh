# Local Guide Source Material

本目录集中保存用于推导战斗行为的攻略素材（全部来自 UP 主「打游戏的老二」）。所有视频统一放在
`videos/`，不再分散到其他文件夹。

## 攻略清单

| 角色/主题 | Bilibili ID | 标题 | 字幕 |
| --- | --- | --- | --- |
| 白藏 | `BV1dB5Y6xE2q` | 神秘翻滚男，白藏详细攻略 | `白藏攻略字幕.txt` |
| 早雾 | `BV16o5P6DEru` | 早雾详细攻略 | `早雾攻略字幕.txt` |
| 达芙蒂尔 | `BV1vHLb61Ewb` | 达芙蒂尔详细攻略 | `达芙蒂尔攻略字幕.txt` |
| 小吱 | `BV1nw9iBKEVF` | 挣钱能手，小吱详细攻略 | `小吱详细攻略 BV1nw9iBKEVF.ai-zh.srt` |
| 九原 | `BV1v9RJBJELv` | 九原详细攻略 | `九原详细攻略 BV1v9RJBJELv.ai-zh.srt` |
| 队伍手法 | `BV1xQVe6kERe` | 安魂曲+达芙蒂尔+早雾+哈尼娅 排轴手法 | `安魂曲达芙蒂尔早雾哈尼娅手法 BV1xQVe6kERe.ai-zh.srt` |

队伍手法视频的主 C 是安魂曲（用户没有），其余三名辅助与白藏竞速队相同；只用于借鉴辅助的打法思路，
不直接套用（手操手法未必适合脚本）。

## 文件说明

- `videos/*.mp4`：原始视频，约 670MB+，**不入 git**（已在 `.gitignore`）。
- `videos/*.jpg`：视频封面，随 videos/ 一并忽略。
- `*.txt`：前三条攻略的人工整理字幕（无时间轴）。
- `*.ai-zh.srt`：后三条攻略的 AI 中文字幕，**带时间轴**，可直接用于建立手法时间线。
- `*.info.json`：yt-dlp 下载元数据（含过期链接，无保留价值），**不入 git**。

## 使用方式

先读字幕（`.srt` 有时间轴），再只看相关视频片段。攻略一律视为**外部设计候选**：任何战斗代码改动
仍需仓库测试 + 对应版本的实机录像才能确认为已验证行为。研究结论沉淀到 `docs/research/` 下对应角色
文档（如 `baicang.md`），并标注 `[EXTERNAL]` / `[UNVERIFIED]`。

## 研究成果（机制提炼）

从上述字幕提炼的机制研究文档，位于上一级 `docs/research/`：

| 文档 | 来源 | 内容 |
| --- | --- | --- |
| `baicang.md` | `BV1dB5Y6xE2q` | 白藏翻滚攻击核心机制、E 三形态、言灵字与大招 |
| `chiz.md` | `BV1nw9iBKEVF` | 小吱本金/贷款、K 线涨跌、E 点按 vs 长按、觉醒 |
| `jiuyuan.md` | `BV1v9RJBJELv` | 九原附着物/玫瑰子弹/清算、E 聚怪、Q 400% 清算 |
| `team_rotation_reference.md` | `BV1xQVe6kERe` | 安魂曲队三辅助排轴（白藏竞速队借鉴，不可照搬） |
| `hania.md` / `daphneel.md` / `adler.md` | 早期攻略 | 各辅助基础机制 |
