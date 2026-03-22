---
name: write-daily-journal
description: 将保存下来的 JSONL 活动数据集整理成单日或日期区间的 Markdown 日记。适用于 Codex 需要读取一个或多个原始 JSONL 文件，提取用户在某一天、昨天、过去一周或过去一个月里做了什么，并在有相关字段时总结情绪、状态或能量线索，直接基于原始记录生成 .md 日记输出的场景。
---

# 写每日/区间日记

从原始 JSONL 数据中提取单日或一段时间内的事件，先生成基于事实的草稿，再在不捏造细节的前提下整理成可读的日记。

## 工作流程

1. 先抽样查看源 JSONL 的 10 到 20 行内容，再决定怎么跑。
2. 判断脚本内置的字段猜测是否已经够用。
3. 运行 `scripts/jsonl_to_journal.py`，直接从原始记录生成结构化 Markdown 草稿。
4. 只有在用户明确想要更自然、更像“日记”的语气时，才对草稿做润色。
5. 最终内容里不要加入原始数据无法支持的说法。

## 快速开始

生成某一天的日记：

```bash
python3 scripts/jsonl_to_journal.py \
  --input /path/to/data.jsonl \
  --date 2026-03-23 \
  --timezone Asia/Shanghai \
  --output /path/to/journal/2026-03-23.md
```

当同一天的数据分散在多个文件里时：

```bash
python3 scripts/jsonl_to_journal.py \
  --input /path/to/app.jsonl \
  --input /path/to/notes.jsonl \
  --date 2026-03-23 \
  --timezone Asia/Shanghai \
  --output /path/to/journal/2026-03-23.md
```

在 Windows PowerShell 下，优先输出到文件，并在预览 JSONL 时始终使用显式 UTF-8：

```powershell
py .\scripts\jsonl_to_journal.py `
  --input C:\data\events.jsonl `
  --date 2026-03-23 `
  --timezone "China Standard Time" `
  --output C:\journal\2026-03-23.md
```

直接从原始 JSONL 生成一段时间的日记：

```bash
python3 scripts/jsonl_to_journal.py \
  --input /path/to/data.jsonl \
  --date-from 2026-03-01 \
  --date-to 2026-03-31 \
  --timezone Asia/Shanghai \
  --output /path/to/journal/2026-03-01_to_2026-03-31.md
```

## 适配数据集

优先使用脚本内置的默认字段猜测。它目前会主动尝试识别这些常见键名：

- `timestamp`, `time`, `created_at`
- `text`, `content`, `message`, `summary`
- `mood`, `emotion`, `state`
- `energy`, `focus`, `fatigue`
- `tags`, `labels`
- `project`, `app`, `tool`, `channel`

跨平台说明：

- 脚本既支持 `Asia/Shanghai` 这种 IANA 时区名，也支持 `China Standard Time` 这种常见 Windows 时区名。
- 输入编码默认使用 `utf-8-sig`，因此普通 UTF-8 和带 BOM 的 UTF-8 文件都能读取。
- 在 Windows PowerShell 下生成最终日记时，优先使用 `--output` 输出到文件，而不是依赖 stdout。
- 区间模式仍然直接读取原始 JSONL 记录，不会去读取之前已经生成过的 Markdown 日记。
- 它可以直接读取当前 VocoType 的数据集格式：`dataset.jsonl` 每行包含 `audio`、`text`、`raw_text`，时间戳会从类似 `2026-03-23_09-30-00.wav` 这样的音频文件名里反推出来。

只有在下面这些情况出现时，才去读 [references/schema-mapping.md](references/schema-mapping.md)：

- 时间戳藏在嵌套字段里
- 正文文本字段名称不是常见名字
- 情绪/能量字段明明存在，但脚本没有识别出来
- 同一个数据集里混了多种 schema

## 输出规则

- 单日模式优先按 `YYYY-MM-DD.md` 命名。
- 区间模式优先按 `YYYY-MM-DD_to_YYYY-MM-DD.md` 命名。
- 把脚本输出当作事实来源，不要拿已有日记覆盖它。
- 所有推断都要明确标成推断；如果数据里没有明确的状态字段，就直说没有。
- 重复记录不要出现在最终日记里。
- 需要幂等时，重复运行应写回同一个输出路径。
- 对 `昨天`、`过去一周` 这类相对时间，先解析成精确日期，再用 `--date` 或 `--date-from/--date-to` 调脚本。

## 润色草稿

脚本跑完以后，润色时仍然要以原始数据为准：

- 保留具体活动、时间点、标签和显式状态字段。
- 重复且价值不高的事件可以合并成更短的表达。
- 明确区分事实和解释。
- 如果用户想要更像“日记”的语气，可以把结构化草稿改写成短段落加简短时间线。
- 如果用户更偏好“数据驱动”的风格，就保留结构化章节，不要过度文学化。

如果用户想换一种日记写法，或者要更明确的成文约束，再去读 [references/journal-structure.md](references/journal-structure.md)。

## 自动化边界

这个 skill 只负责“如何把原始记录整理成日记”。如果用户想每天定时运行，需要另外配置 automation。调度时间、工作区、输入路径和输出目录都应放在 automation 配置里，而不是写死在 skill 说明里。
