# Schema 映射

只有在脚本内置的字段猜测不够用时，才读这个文件。

## 目标

把用户自己的 JSONL schema 映射到脚本的标准字段上：

- `timestamp`
- `text`
- `mood`
- `energy`
- `tags`
- `project`

## 怎么检查

脚本默认直接读取 VocoType 固定数据集路径。排查字段时，先预览前几行：

```bash
sed -n '1,20p' ~/Library/Application\ Support/VocoType/dataset/dataset.jsonl
```

```powershell
Get-Content -Path "$env:APPDATA\VocoType\dataset\dataset.jsonl" -Encoding UTF8 -TotalCount 20
```

重点看这几件事：

- 哪个字段表示事件时间
- 哪个字段是主要文本内容
- 有没有情绪、能量、标签、项目这些字段
- 数据是平铺结构还是嵌套结构

## 字段映射文件格式

把一个 JSON 文件传给 `--field-map`。每个值都可以是一个点路径，或者一组点路径。

示例：

```json
{
  "timestamp": ["event.created_at", "meta.ts"],
  "text": ["event.summary", "event.text"],
  "mood": "signals.mood",
  "energy": "signals.energy",
  "tags": ["event.tags", "labels"],
  "project": ["context.project", "context.app"]
}
```

## 说明

- 嵌套对象请使用点路径，比如 `event.summary`。
- 列表索引也支持，比如 `items.0.text`。
- 只覆盖确实需要改的字段即可；没写的字段仍然会使用脚本默认值。
- 如果一个数据集里混了多种 schema，就把多个候选路径按优先级顺序写进去。
- 如果 JSONL 文件是在 Windows 上写出来的，UTF-8 BOM 也是可以接受的；脚本默认就能读。

## 实用原则

如果时间戳和正文文本没有对上，先停下来修这两个字段。`mood` 和 `energy` 不是必需项；只要时间和活动文本能正确识别，依然可以生成可用的日记。
