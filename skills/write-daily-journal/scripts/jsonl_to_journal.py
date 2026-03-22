#!/usr/bin/env python3

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import re
import sys
from dataclasses import dataclass
from typing import Any, Iterable
from zoneinfo import ZoneInfo
from zoneinfo import ZoneInfoNotFoundError


DEFAULT_FIELD_MAP: dict[str, list[str]] = {
    "timestamp": [
        "timestamp",
        "time",
        "ts",
        "created_at",
        "createdAt",
        "datetime",
        "date",
        "occurred_at",
        "event_time",
        "eventTime",
        "meta.timestamp",
        "metadata.timestamp",
        "audio",
        "audio_file",
        "file",
        "filename",
    ],
    "text": [
        "text",
        "content",
        "message",
        "summary",
        "note",
        "description",
        "event",
        "activity",
        "title",
        "body",
    ],
    "mood": [
        "mood",
        "emotion",
        "feeling",
        "state",
        "status",
    ],
    "energy": [
        "energy",
        "focus",
        "fatigue",
        "stamina",
        "attention",
    ],
    "tags": [
        "tags",
        "labels",
        "topics",
        "categories",
    ],
    "project": [
        "project",
        "app",
        "tool",
        "channel",
        "source",
        "workspace",
    ],
}

COMMON_DT_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d",
)

FILENAME_DT_FORMATS = (
    "%Y-%m-%d_%H-%M-%S",
    "%Y-%m-%d-%H-%M-%S",
    "%Y%m%d_%H%M%S",
    "%Y%m%d-%H%M%S",
)

WINDOWS_TZ_MAP: dict[str, str] = {
    "utc": "UTC",
    "dateline standard time": "Etc/GMT+12",
    "utc-11": "Etc/GMT+11",
    "aleutian standard time": "America/Adak",
    "hawaiian standard time": "Pacific/Honolulu",
    "alaskan standard time": "America/Anchorage",
    "pacific standard time": "America/Los_Angeles",
    "us mountain standard time": "America/Phoenix",
    "mountain standard time": "America/Denver",
    "central standard time": "America/Chicago",
    "eastern standard time": "America/New_York",
    "atlantic standard time": "America/Halifax",
    "greenwich standard time": "Atlantic/Reykjavik",
    "gmt standard time": "Europe/London",
    "w. europe standard time": "Europe/Berlin",
    "romance standard time": "Europe/Paris",
    "e. europe standard time": "Europe/Bucharest",
    "turkey standard time": "Europe/Istanbul",
    "israel standard time": "Asia/Jerusalem",
    "arabian standard time": "Asia/Dubai",
    "russian standard time": "Europe/Moscow",
    "india standard time": "Asia/Kolkata",
    "se asia standard time": "Asia/Bangkok",
    "china standard time": "Asia/Shanghai",
    "tokyo standard time": "Asia/Tokyo",
    "korea standard time": "Asia/Seoul",
    "aus eastern standard time": "Australia/Sydney",
    "new zealand standard time": "Pacific/Auckland",
}


@dataclass
class Event:
    bucket_date: dt.date
    local_time: dt.datetime | None
    text: str
    mood: str | None
    energy: str | float | None
    tags: list[str]
    project: str | None
    source_file: str
    line_number: int
    fingerprint: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read VocoType's fixed dataset.jsonl path and render a Markdown journal draft."
    )
    parser.add_argument(
        "--date",
        help="Target local date in YYYY-MM-DD.",
    )
    parser.add_argument(
        "--date-from",
        help="Inclusive start date in YYYY-MM-DD for range mode.",
    )
    parser.add_argument(
        "--date-to",
        help="Inclusive end date in YYYY-MM-DD for range mode.",
    )
    parser.add_argument(
        "--output",
        help="Output Markdown path. Prints to stdout when omitted.",
    )
    parser.add_argument(
        "--timezone",
        help="IANA timezone name such as Asia/Shanghai. Windows timezone names such as China Standard Time are also accepted.",
    )
    parser.add_argument(
        "--input-encoding",
        default="utf-8-sig",
        help="Input JSONL encoding. Defaults to utf-8-sig so UTF-8 and UTF-8 BOM files both work.",
    )
    parser.add_argument(
        "--day-start-hour",
        type=int,
        default=0,
        help="Treat records before this local hour as belonging to the previous day.",
    )
    parser.add_argument(
        "--field-map",
        help="Optional JSON file that overrides field candidate lists.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=12,
        help="Maximum items shown in the activity and timeline sections.",
    )
    parser.add_argument(
        "--allow-untimed",
        action="store_true",
        help="Include records without a usable timestamp and attach them to the target date.",
    )
    return parser.parse_args()


def default_dataset_path() -> pathlib.Path:
    if sys.platform == "darwin":
        base_dir = pathlib.Path.home() / "Library" / "Application Support"
    elif sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            base_dir = pathlib.Path(appdata)
        else:
            base_dir = pathlib.Path.home() / "AppData" / "Roaming"
    else:
        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        if xdg_data_home:
            base_dir = pathlib.Path(xdg_data_home)
        else:
            base_dir = pathlib.Path.home() / ".local" / "share"
    return base_dir / "VocoType" / "dataset" / "dataset.jsonl"


def get_local_timezone() -> tuple[dt.tzinfo, str]:
    now = dt.datetime.now().astimezone()
    local_tz = now.tzinfo or dt.timezone.utc
    label = getattr(local_tz, "key", None) or now.tzname() or "local"
    return local_tz, label


def resolve_timezone(requested: str | None) -> tuple[dt.tzinfo, str]:
    local_tz, local_label = get_local_timezone()
    if not requested or requested.lower() in {"local", "system"}:
        return local_tz, local_label

    normalized = requested.strip()
    if not normalized:
        return local_tz, local_label

    candidates = [normalized]
    mapped = WINDOWS_TZ_MAP.get(normalized.lower())
    if mapped and mapped not in candidates:
        candidates.append(mapped)

    for candidate in candidates:
        if candidate.upper() == "UTC":
            return dt.timezone.utc, "UTC"
        try:
            return ZoneInfo(candidate), candidate
        except ZoneInfoNotFoundError:
            continue

    if normalized.lower() == local_label.lower():
        return local_tz, local_label

    message = "Use an IANA name like Asia/Shanghai, or a Windows name like China Standard Time."
    raise SystemExit(f"unsupported timezone '{requested}'. {message}")


def parse_requested_range(args: argparse.Namespace, timezone: dt.tzinfo) -> tuple[dt.date, dt.date]:
    if args.date and (args.date_from or args.date_to):
        raise SystemExit("use either --date or --date-from/--date-to, not both")

    if args.date:
        target = dt.date.fromisoformat(args.date)
        return target, target

    start = dt.date.fromisoformat(args.date_from) if args.date_from else None
    end = dt.date.fromisoformat(args.date_to) if args.date_to else None

    if start is None and end is None:
        today = dt.datetime.now(timezone).date()
        return today, today
    if start is None:
        start = end
    if end is None:
        end = start
    if start > end:
        raise SystemExit("--date-from must be earlier than or equal to --date-to")
    return start, end


def load_field_map(path: str | None) -> dict[str, list[str]]:
    merged = {key: values[:] for key, values in DEFAULT_FIELD_MAP.items()}
    if not path:
        return merged
    data = json.loads(pathlib.Path(path).expanduser().read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("field-map must be a JSON object")
    for key, value in data.items():
        if isinstance(value, str):
            merged[key] = [value]
        elif isinstance(value, list) and all(isinstance(item, str) for item in value):
            merged[key] = value
        else:
            raise ValueError(f"field-map entry '{key}' must be a string or a list of strings")
    return merged


def get_nested_value(record: Any, path: str) -> Any:
    current = record
    for segment in path.split("."):
        if isinstance(current, dict) and segment in current:
            current = current[segment]
            continue
        if isinstance(current, list) and segment.isdigit():
            index = int(segment)
            if 0 <= index < len(current):
                current = current[index]
                continue
        return None
    return current


def first_non_empty(record: dict[str, Any], candidates: Iterable[str]) -> Any:
    for path in candidates:
        value = get_nested_value(record, path)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        return value
    return None


def coerce_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        compact = " ".join(value.split())
        return compact or None
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        pieces = [coerce_text(item) for item in value]
        joined = "; ".join(piece for piece in pieces if piece)
        return joined or None
    if isinstance(value, dict):
        for key in ("text", "content", "message", "summary", "title"):
            nested = value.get(key)
            text = coerce_text(nested)
            if text:
                return text
        compact = json.dumps(value, ensure_ascii=False, sort_keys=True)
        return compact
    return str(value)


def coerce_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[，,;/|]", value)
        return [part.strip() for part in parts if part.strip()]
    if isinstance(value, list):
        tags = [coerce_text(item) for item in value]
        return [tag for tag in tags if tag]
    text = coerce_text(value)
    return [text] if text else []


def parse_numeric(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if math.isfinite(float(value)):
            return float(value)
        return None
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value)
        if match:
            return float(match.group(0))
    return None


def parse_datetime(value: Any, timezone: dt.tzinfo) -> dt.datetime | None:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        current = value
    elif isinstance(value, dt.date):
        current = dt.datetime.combine(value, dt.time())
    elif isinstance(value, (int, float)):
        seconds = float(value)
        if abs(seconds) > 1_000_000_000_000:
            seconds /= 1000.0
        current = dt.datetime.fromtimestamp(seconds, tz=dt.timezone.utc)
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if re.fullmatch(r"\d{10,13}", raw):
            seconds = float(raw)
            if len(raw) == 13:
                seconds /= 1000.0
            current = dt.datetime.fromtimestamp(seconds, tz=dt.timezone.utc)
        else:
            normalized = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
            try:
                current = dt.datetime.fromisoformat(normalized)
            except ValueError:
                current = None
                for fmt in COMMON_DT_FORMATS:
                    try:
                        current = dt.datetime.strptime(raw, fmt)
                        break
                    except ValueError:
                        continue
                if current is None:
                    return None
    else:
        return None

    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone)
    return current.astimezone(timezone)


def parse_datetime_from_filename(value: Any, timezone: dt.tzinfo) -> dt.datetime | None:
    text = coerce_text(value)
    if not text:
        return None
    filename = re.split(r"[\\\\/]", text)[-1]
    stem = filename.rsplit(".", 1)[0]
    for fmt in FILENAME_DT_FORMATS:
        try:
            current = dt.datetime.strptime(stem, fmt)
            return current.replace(tzinfo=timezone)
        except ValueError:
            continue
    return None


def extract_event_datetime(
    record: dict[str, Any],
    field_map: dict[str, list[str]],
    timezone: dt.tzinfo,
) -> dt.datetime | None:
    direct = parse_datetime(first_non_empty(record, field_map["timestamp"]), timezone)
    if direct is not None:
        return direct

    # VocoType dataset.jsonl stores local time in the audio filename such as 2026-03-23_09-30-00.wav.
    for candidate in ("audio", "audio_file", "file", "filename"):
        inferred = parse_datetime_from_filename(record.get(candidate), timezone)
        if inferred is not None:
            return inferred
    return None


def bucket_date(local_time: dt.datetime | None, fallback: dt.date, day_start_hour: int) -> dt.date | None:
    if local_time is None:
        return fallback if fallback else None
    shifted = local_time
    if 0 <= day_start_hour <= 23 and local_time.hour < day_start_hour:
        shifted = local_time - dt.timedelta(days=1)
    return shifted.date()


def event_fingerprint(local_time: dt.datetime | None, text: str) -> str:
    minute_bucket = local_time.strftime("%Y-%m-%d %H:%M") if local_time else "no-time"
    payload = f"{minute_bucket}\n{text.lower()}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def normalize_event(
    record: dict[str, Any],
    source_file: pathlib.Path,
    line_number: int,
    start_date: dt.date,
    end_date: dt.date,
    field_map: dict[str, list[str]],
    timezone: dt.tzinfo,
    day_start_hour: int,
    allow_untimed: bool,
) -> Event | None:
    local_time = extract_event_datetime(record, field_map, timezone)
    single_day = start_date == end_date
    fallback_date = start_date if allow_untimed and single_day else None
    date_for_bucket = bucket_date(local_time, fallback_date, day_start_hour)
    if date_for_bucket is None:
        return None
    if date_for_bucket < start_date or date_for_bucket > end_date:
        return None

    text_value = coerce_text(first_non_empty(record, field_map["text"]))
    if not text_value:
        text_value = coerce_text(record)
    if not text_value:
        return None

    mood = coerce_text(first_non_empty(record, field_map["mood"]))
    raw_energy = first_non_empty(record, field_map["energy"])
    numeric_energy = parse_numeric(raw_energy)
    energy: str | float | None = numeric_energy if numeric_energy is not None else coerce_text(raw_energy)
    tags = coerce_tags(first_non_empty(record, field_map["tags"]))
    project = coerce_text(first_non_empty(record, field_map["project"]))

    return Event(
        bucket_date=date_for_bucket,
        local_time=local_time,
        text=text_value,
        mood=mood,
        energy=energy,
        tags=tags,
        project=project,
        source_file=str(source_file),
        line_number=line_number,
        fingerprint=event_fingerprint(local_time, text_value),
    )


def read_events(
    paths: list[pathlib.Path],
    start_date: dt.date,
    end_date: dt.date,
    field_map: dict[str, list[str]],
    timezone: dt.tzinfo,
    day_start_hour: int,
    allow_untimed: bool,
    input_encoding: str,
) -> tuple[list[Event], dict[str, int]]:
    stats = collections.Counter()
    deduped: dict[str, Event] = {}

    for path in paths:
        stats["files"] += 1
        with path.open("r", encoding=input_encoding) as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                stats["lines"] += 1
                try:
                    record = json.loads(stripped)
                except json.JSONDecodeError:
                    stats["invalid_json"] += 1
                    continue
                if not isinstance(record, dict):
                    stats["non_object"] += 1
                    continue
                event = normalize_event(
                    record=record,
                    source_file=path,
                    line_number=line_number,
                    start_date=start_date,
                    end_date=end_date,
                    field_map=field_map,
                    timezone=timezone,
                    day_start_hour=day_start_hour,
                    allow_untimed=allow_untimed,
                )
                if event is None:
                    stats["filtered_out"] += 1
                    continue
                if event.fingerprint in deduped:
                    stats["duplicates"] += 1
                    continue
                deduped[event.fingerprint] = event
                stats["matched"] += 1

    events = sorted(
        deduped.values(),
        key=lambda item: (
            item.local_time is None,
            item.local_time or dt.datetime.max.replace(tzinfo=timezone),
            item.text,
        ),
    )
    return events, dict(stats)


def summarize_projects(events: list[Event], limit: int = 5) -> list[str]:
    counter = collections.Counter()
    for event in events:
        if event.project:
            counter[event.project] += 1
        for tag in event.tags:
            counter[tag] += 1
    return [f"{name} ({count})" for name, count in counter.most_common(limit)]


def group_events_by_date(events: list[Event]) -> list[tuple[dt.date, list[Event]]]:
    grouped: dict[dt.date, list[Event]] = collections.OrderedDict()
    for event in events:
        grouped.setdefault(event.bucket_date, []).append(event)
    return list(grouped.items())


def format_time_span(events: list[Event]) -> str | None:
    timed = [event.local_time for event in events if event.local_time is not None]
    if not timed:
        return None
    return f"{timed[0].strftime('%H:%M')} - {timed[-1].strftime('%H:%M')}"


def summarize_windows(events: list[Event]) -> str | None:
    if not events:
        return None
    counter = collections.Counter()
    for event in events:
        if event.local_time is None:
            continue
        hour = event.local_time.hour
        if hour < 12:
            counter["上午"] += 1
        elif hour < 18:
            counter["下午"] += 1
        else:
            counter["晚上"] += 1
    if not counter:
        return None
    ordered = [name for name, _count in counter.most_common()]
    return "、".join(ordered)


def summarize_status(events: list[Event]) -> list[str]:
    lines: list[str] = []
    moods = [event.mood for event in events if event.mood]
    if moods:
        counter = collections.Counter(moods)
        lines.append("明确状态记录：" + "、".join(f"{name} ({count})" for name, count in counter.most_common(5)))

    energy_values = [event.energy for event in events if isinstance(event.energy, float)]
    if energy_values:
        average = sum(energy_values) / len(energy_values)
        lines.append(f"数值化能量/专注：平均 {average:.2f}（共 {len(energy_values)} 条）")
    else:
        energy_texts = [event.energy for event in events if isinstance(event.energy, str)]
        if energy_texts:
            counter = collections.Counter(energy_texts)
            lines.append("文本状态线索：" + "、".join(f"{name} ({count})" for name, count in counter.most_common(5)))

    windows = summarize_windows(events)
    if windows:
        lines.append(f"记录主要集中在：{windows}")

    if not lines:
        lines.append("没有提取到明确的状态字段，只保留活动事实，不额外推断情绪。")
    return lines


def format_event_line(event: Event) -> str:
    prefix = event.local_time.strftime("%H:%M") if event.local_time else "时间未知"
    extras: list[str] = []
    if event.project:
        extras.append(event.project)
    if event.tags:
        extras.append("标签: " + " / ".join(event.tags[:4]))
    extra_text = f" ({'; '.join(extras)})" if extras else ""
    return f"- {prefix} {event.text}{extra_text}"


def build_activity_lines(events: list[Event], max_items: int) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for event in events:
        dedupe_key = event.text.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        items.append(format_event_line(event))
        if len(items) >= max_items:
            break
    return items


def build_daily_markdown(
    target_date: dt.date,
    timezone_name: str,
    events: list[Event],
    stats: dict[str, int],
    max_items: int,
) -> str:
    lines: list[str] = []
    lines.append(f"# {target_date.isoformat()} 日记")
    lines.append("")
    lines.append("> 基于 JSONL 数据自动整理生成；事实优先，推断从严。")
    lines.append("")
    lines.append("## 今日概览")
    matched = stats.get("matched", 0)
    duplicates = stats.get("duplicates", 0)
    invalid = stats.get("invalid_json", 0) + stats.get("non_object", 0)
    lines.append(f"- 有效记录：{matched}")
    lines.append(f"- 去重记录：{duplicates}")
    lines.append(f"- 跳过异常行：{invalid}")
    lines.append(f"- 时区：{timezone_name}")
    span = format_time_span(events)
    if span:
        lines.append(f"- 记录时间跨度：{span}")
    projects = summarize_projects(events)
    if projects:
        lines.append("- 主要项目/标签：" + "、".join(projects))
    else:
        lines.append("- 主要项目/标签：未提取到明确标签")
    lines.append("")
    lines.append("## 今天做了什么")
    if events:
        activity_lines = build_activity_lines(events, max_items)
        for line in activity_lines:
            lines.append(line)
        if len(activity_lines) < len(events):
            lines.append(f"- 其余 {len(events) - len(activity_lines)} 条记录已省略，可按需查看原始数据。")
    else:
        lines.append("- 当天没有提取到可归档的事件。")
    lines.append("")
    lines.append("## 今日状态")
    for item in summarize_status(events):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## 时间线")
    if events:
        for event in events[:max_items]:
            lines.append(format_event_line(event))
    else:
        lines.append("- 无时间线数据。")
    lines.append("")
    lines.append("## 数据质量备注")
    if not events:
        lines.append("- 没有匹配到目标日期的记录，请检查日期、时区、字段映射或 day-start-hour 设置。")
    else:
        lines.append("- 同一分钟内完全相同的文本会按重复记录去重。")
        lines.append("- 默认跳过没有可用时间戳的记录；只有传入 `--allow-untimed` 时才会纳入结果。")
        lines.append("- 如果状态字段缺失，脚本不会主观推断心理状态。")
    return "\n".join(lines) + "\n"


def build_range_markdown(
    start_date: dt.date,
    end_date: dt.date,
    timezone_name: str,
    events: list[Event],
    stats: dict[str, int],
    max_items: int,
) -> str:
    lines: list[str] = []
    lines.append(f"# {start_date.isoformat()} 到 {end_date.isoformat()} 日记")
    lines.append("")
    lines.append("> 基于原始 JSONL 数据直接整理生成；未读取已有日记做二次汇总。")
    lines.append("")
    lines.append("## 区间概览")
    lines.append(f"- 日期范围：{start_date.isoformat()} 到 {end_date.isoformat()}")
    lines.append(f"- 覆盖天数：{(end_date - start_date).days + 1}")
    lines.append(f"- 有记录的天数：{len(group_events_by_date(events))}")
    lines.append(f"- 有效记录：{stats.get('matched', 0)}")
    lines.append(f"- 去重记录：{stats.get('duplicates', 0)}")
    lines.append(f"- 跳过异常行：{stats.get('invalid_json', 0) + stats.get('non_object', 0)}")
    lines.append(f"- 时区：{timezone_name}")
    projects = summarize_projects(events)
    if projects:
        lines.append("- 主要项目/标签：" + "、".join(projects))
    else:
        lines.append("- 主要项目/标签：未提取到明确标签")
    lines.append("")
    lines.append("## 区间状态")
    for item in summarize_status(events):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## 每日整理")
    grouped_events = group_events_by_date(events)
    if not grouped_events:
        lines.append("- 区间内没有匹配到可归档的事件。")
    else:
        for day, day_events in grouped_events:
            lines.append(f"### {day.isoformat()}")
            lines.append(f"- 记录数：{len(day_events)}")
            span = format_time_span(day_events)
            if span:
                lines.append(f"- 时间跨度：{span}")
            projects = summarize_projects(day_events)
            if projects:
                lines.append("- 主要项目/标签：" + "、".join(projects))
            lines.append("")
            lines.append("#### 今天做了什么")
            activity_lines = build_activity_lines(day_events, max_items)
            for line in activity_lines:
                lines.append(line)
            if len(activity_lines) < len(day_events):
                lines.append(f"- 其余 {len(day_events) - len(activity_lines)} 条记录已省略，可按需查看原始数据。")
            lines.append("")
            lines.append("#### 今日状态")
            for item in summarize_status(day_events):
                lines.append(f"- {item}")
            lines.append("")
            lines.append("#### 时间线")
            for event in day_events[:max_items]:
                lines.append(format_event_line(event))
            lines.append("")
    lines.append("## 数据质量备注")
    if not events:
        lines.append("- 没有匹配到目标日期范围的记录，请检查日期、时区、字段映射或 day-start-hour 设置。")
    else:
        lines.append("- 区间整理直接基于原始 JSONL 记录，不读取已有 Markdown 日记。")
        lines.append("- 同一分钟内完全相同的文本会按重复记录去重。")
        lines.append("- 多日范围下，没有可用时间戳的记录默认跳过，避免误归档到错误日期。")
        lines.append("- 如果状态字段缺失，脚本不会主观推断心理状态。")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    if not 0 <= args.day_start_hour <= 23:
        raise SystemExit("--day-start-hour must be between 0 and 23")

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    timezone, timezone_label = resolve_timezone(args.timezone)
    start_date, end_date = parse_requested_range(args, timezone)
    dataset_path = default_dataset_path()
    if not dataset_path.exists():
        raise SystemExit(f"default dataset file not found: {dataset_path}")

    field_map = load_field_map(args.field_map)
    events, stats = read_events(
        paths=[dataset_path],
        start_date=start_date,
        end_date=end_date,
        field_map=field_map,
        timezone=timezone,
        day_start_hour=args.day_start_hour,
        allow_untimed=args.allow_untimed,
        input_encoding=args.input_encoding,
    )
    if start_date == end_date:
        markdown = build_daily_markdown(
            target_date=start_date,
            timezone_name=timezone_label,
            events=events,
            stats=stats,
            max_items=max(1, args.max_items),
        )
    else:
        markdown = build_range_markdown(
            start_date=start_date,
            end_date=end_date,
            timezone_name=timezone_label,
            events=events,
            stats=stats,
            max_items=max(1, args.max_items),
        )

    if args.output:
        output_path = pathlib.Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
    else:
        sys.stdout.write(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
