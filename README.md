# vocotype-journal-skills

VocoType 相关的 Codex skills 仓库。

当前包含：

- `skills/write-daily-journal`

这个 skill 用来直接读取 VocoType 保存下来的原始 `dataset.jsonl` 数据集，按单日或日期区间生成 Markdown 日记，不依赖已有日记做二次整理。

## 仓库结构

```text
skills/
  write-daily-journal/
    SKILL.md
    agents/openai.yaml
    scripts/jsonl_to_journal.py
    references/
```

## 安装

如果本机已经有 Codex，可以从 GitHub 仓库安装：

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo 233stone/vocotype-journal-skills \
  --path skills/write-daily-journal
```

安装后重启 Codex，让新 skill 生效。

## 数据集路径

默认适配当前 VocoType 的数据集格式：

- macOS: `~/Library/Application Support/VocoType/dataset/dataset.jsonl`
- Windows: `%APPDATA%\\VocoType\\dataset\\dataset.jsonl`

## 当前能力

- 直接读取原始 JSONL
- 支持单日整理
- 支持区间整理
- 支持从 VocoType 的音频文件名反推出时间
- 兼容 macOS / Windows 常见路径与时区写法
