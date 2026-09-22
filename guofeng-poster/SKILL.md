---
name: guofeng-poster
description: 用户输入一个地名（城市/区县/乡镇），自动联网调研该地真实文化符号，生成一套「国风城市电影海报」文生图提示词，并用 ImageGen 出底图 + PIL 矢量叠加精确中文文字，产出一幅带完整左侧文字栏的 9:16 国风文旅海报。触发词：国风海报、城市海报、家乡海报、地名海报、文旅海报、电影感城市海报。
---

# 国风城市电影海报生成技能

用户输入一个**地名**，本技能产出：① 一套可直接复用的完整文生图提示词；② 一幅 9:16 国风电影感城市海报（底图由 ImageGen 生成，左侧 30% 中文文字栏由 `compose.py` 用 PIL 矢量精确叠加，杜绝 AI 出图中文乱码）。

## 适用场景
- 把家乡 / 旅游城市做成国风收藏级海报
- 文旅宣传、班级/学校地域文化作业、自媒体配图
- 想要「换个地名就能用」的可复用国风模板

## 核心工作流（严格按顺序）

### 1. 接收地名
从用户消息提取目标城市/地名，例如「苏州」。若用户没给，先追问。

### 2. 联网调研真实素材（关键，禁止虚构）
用 `WebSearch` 查证该地的**真实**信息（不确定就搜，不要凭印象编）：
- 代表性自然景观（湖/山/江/海/园林…）
- 三大标志性建筑（第一/第二/第三地标）
- 传统建筑风格（白墙黛瓦 / 骑楼 / 石库门 / 红砖燕尾脊…）
- 市花 / 代表性花卉、代表性植物、代表性鸟类或动物
- 非遗项目、地方工艺（苏绣 / 扎染 / 木雕 / 瓷器…）
- 特色食物 2 种、特色饮品 1 种
- 代表性人物身份（绣娘 / 茶艺师 / 评弹艺人 / 渔民…）及其服饰主色与动作
- 英文城市名、所属省份（英文）
- 城市意象关键词（用于四字印象 / 四字主标题 / 四字意象）

> 铁律：所有【】内容必须与城市**真实**对应；禁止混用不同城市地标、禁止混用民族服饰。

### 3. 填模板 → 得到文生图提示词
读取本技能 `references/template.md`，把其中所有【】逐条替换为调研结果，拼成**完整英文 image prompt**（文生图模型对英文理解更好，建议整段英文；中文专名保留拼音+意译）。

输出给用户时，把这套完整提示词**原文展示**出来（用户要的就是「提示词」），并说明下一步要出图。

### 4. 出底图（ImageGen）
⚠️ **出图前必须告知用户：单次 ImageGen 约消耗 5–10 credits。**
调用 ImageGen 工具：
- `prompt`：第 3 步拼好的完整提示词
- `size`：`"1024x1536"`（9:16 竖版）
- `quality`：`"high"`
- `style`：可留空或 `"Chinese ink painting, watercolor illustration"`
- `output_dir`：指定一个工作目录（如 `%TEMP%/guofeng_poster/`）
- 不要加 `footnote`（中文水印会乱码，文字统一后加）

### 5. 写文字 spec(JSON) 并叠加中文
把左侧文字栏所有字段写进一个 `spec.json`（字段见下），然后运行 `compose.py`：

```bash
# 自动选择 Python：优先用 WorkBuddy 托管 venv，否则用系统 python3，缺失 Pillow 时自动安装
PY="$HOME/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
[ -x "$PY" ] || PY="$(command -v python3 || command -v python)"
"$PY" -c "import PIL" 2>/dev/null || "$PY" -m pip install --quiet pillow
"$PY" "$HOME/.workbuddy/skills/guofeng-poster/compose.py" \
  --image <ImageGen生成的底图.png> \
  --spec <spec.json> \
  --out <最终海报.png> \
  --panel-ratio 0.30
```

> 若你机器上字体不在 `C:/Windows/Fonts`（如非 Windows 系统），可设置环境变量 `GF_POSTER_FONT_DIR` 指向你的中文字体目录，compose.py 会优先从那里读取。

`spec.json` 字段（缺省留空串即可）：
```json
{
  "year": "2026",
  "city_impression": "江南姑苏",
  "en_city": "SUZHOU · CHINA",
  "main_title": "姑苏烟雨",
  "china_city": "中国苏州",
  "subtitle": ["园林之城", "太湖之畔", "千年雅韵"],
  "intro_cn": ["粉墙黛瓦，枕河人家。", "亭台倒影，曲廊通幽。", "一曲评弹，半城烟水。", "此处最江南。"],
  "en_location": "SUZHOU, JIANGSU, CHINA",
  "en_intro": ["A classical garden city by Taihu Lake.", "Where water towns meet a thousand years of elegance."],
  "summary_cn": "江南雅韵 · 园林之城",
  "summary_en": "Suzhou — The Paradise of Gardens",
  "icon": "pagoda"
}
```
`icon` 可选：`pagoda`(塔) / `mountain`(山水) / `bridge`(桥) / `leaf`(花叶) / `lantern`(灯)。

### 6. 交付
把最终 PNG 用 `present_files` 展示给用户，并附上第 3 步的完整提示词文本（用户可能需要复用/微调）。

## 设计铁律（务必遵守）
1. **左侧中文绝不靠 AI 出图**：文生图模型对中文几乎必出乱码。`compose.py` 会先把左侧 30% 重绘为干净暖白宣纸面板（右缘羽化融入右侧画面），再用矢量字体叠加全部中文/英文/印章，保证清晰可读。
2. **真实优先**：地标、食物、非遗、服饰必须与城市对应；不确定的用 WebSearch 查证。
3. **硬性禁止项**（来自模板，写进 prompt 即可）：侧脸剪影、双重曝光、九宫格拼贴、景物穿模、建筑变形、地标混用、民族服饰混用、多指/断指、霓虹色、塑料感 3D、水印、品牌 Logo、中文乱码。
4. **构图分区**：右上方自然景观+地标 / 中部传统建筑街区 / 右下方人物+非遗+风物；整体 S 形动线。

## 字体依赖（Windows 自带，免安装）
`compose.py` 优先使用：`msyh.ttc`(雅黑)、`simsun.ttc`(宋体)、`simkai.ttf`(楷体)、`STXINGKA.TTF`(华文行楷·主标题书法感)、`simhei.ttf`(黑体·印章)。任一缺失会自动回退雅黑，正常机器均存在。

## 备注
- 模板原文与替填说明见 `references/template.md`。
- 若想让 AI 直接替填：把 template.md 全文 + 「请按【城市名】替换所有【】」发给任意模型即可。
