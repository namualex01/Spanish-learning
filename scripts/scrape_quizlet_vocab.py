#!/usr/bin/env python3
"""抓取 Quizlet 单词集并导出为 CSV/JSON/TXT。

示例:
python scripts/scrape_quizlet_vocab.py \
  "https://quizlet.com/cn/40125686/.../flash-cards/" \
  --output data/modern_spanish_1_4.csv
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import ssl
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://quizlet.com/",
}


def fetch_html(url: str, timeout: int = 30) -> str:
    req = Request(url, headers=DEFAULT_HEADERS)
    context = ssl.create_default_context()
    with urlopen(req, timeout=timeout, context=context) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def extract_json_blobs(page_html: str) -> list[str]:
    blobs: list[str] = []

    # Next.js 数据
    for m in re.finditer(
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        page_html,
        flags=re.DOTALL,
    ):
        blobs.append(html.unescape(m.group(1)).strip())

    # 其它 script 里的 JSON 字面量
    for m in re.finditer(
        r"(?:window\.__INITIAL_STATE__|__APOLLO_STATE__|__NUXT__|dataLayer)\s*=\s*(\{.*?\});",
        page_html,
        flags=re.DOTALL,
    ):
        blobs.append(html.unescape(m.group(1)).strip())

    return blobs


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def sides_to_pair(sides: Any) -> tuple[str, str] | None:
    if not isinstance(sides, list) or len(sides) < 2:
        return None

    def parse_side(side: Any) -> str:
        if isinstance(side, str):
            return normalize_text(side)
        if not isinstance(side, dict):
            return ""
        if isinstance(side.get("text"), str):
            return normalize_text(side["text"])

        media = side.get("media") or side.get("mediaList") or []
        parts: list[str] = []
        if isinstance(media, list):
            for item in media:
                if not isinstance(item, dict):
                    continue
                for key in ("plainText", "text", "ttsText", "label"):
                    val = item.get(key)
                    if isinstance(val, str) and val.strip():
                        parts.append(normalize_text(val))
                        break
        if parts:
            return normalize_text(" ".join(parts))
        return ""

    left = parse_side(sides[0])
    right = parse_side(sides[1])
    if left and right:
        return left, right
    return None


def maybe_pair(obj: dict[str, Any]) -> tuple[str, str] | None:
    # 常见结构 1：直接 term/definition
    for a, b in [
        ("term", "definition"),
        ("word", "definition"),
        ("front", "back"),
        ("left", "right"),
        ("prompt", "answer"),
    ]:
        va, vb = obj.get(a), obj.get(b)
        if isinstance(va, str) and isinstance(vb, str):
            ta, tb = normalize_text(va), normalize_text(vb)
            if ta and tb:
                return ta, tb

    # 常见结构 2：studiableItemResponses / cardSides
    for key in ("cardSides", "sides", "studiableSides"):
        pair = sides_to_pair(obj.get(key))
        if pair:
            return pair

    return None


def find_pairs(payload: Any) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    stack: list[Any] = [payload]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            pair = maybe_pair(cur)
            if pair and pair not in seen:
                seen.add(pair)
                found.append(pair)
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)

    return found


def extract_pairs(page_html: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []

    for blob in extract_json_blobs(page_html):
        try:
            payload = json.loads(blob)
        except json.JSONDecodeError:
            continue
        pairs.extend(find_pairs(payload))

    # 兜底：从 HTML 中提取 "term":"...","definition":"..."
    if not pairs:
        for term, definition in re.findall(
            r'"term"\s*:\s*"(.*?)"\s*,\s*"definition"\s*:\s*"(.*?)"', page_html
        ):
            t = normalize_text(bytes(term, "utf-8").decode("unicode_escape"))
            d = normalize_text(bytes(definition, "utf-8").decode("unicode_escape"))
            if t and d:
                pairs.append((t, d))

    # 去重保持顺序
    unique: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for pair in pairs:
        if pair in seen:
            continue
        seen.add(pair)
        unique.append(pair)

    return unique


def save_pairs(pairs: list[tuple[str, str]], output: Path, fmt: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "csv":
        with output.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["word", "meaning"])
            writer.writerows(pairs)
        return

    if fmt == "json":
        with output.open("w", encoding="utf-8") as f:
            json.dump(
                [{"word": w, "meaning": m} for w, m in pairs],
                f,
                ensure_ascii=False,
                indent=2,
            )
        return

    if fmt == "txt":
        with output.open("w", encoding="utf-8") as f:
            for w, m in pairs:
                f.write(f"{w} | {m}\n")
        return

    raise ValueError(f"Unsupported format: {fmt}")


def main() -> int:
    parser = argparse.ArgumentParser(description="抓取 Quizlet 单词并导出")
    parser.add_argument("url", help="Quizlet 单词集 URL")
    parser.add_argument("--output", "-o", default="data/quizlet_words.csv", help="输出文件路径")
    parser.add_argument(
        "--format",
        "-f",
        choices=["csv", "json", "txt"],
        default="csv",
        help="输出格式（默认 csv）",
    )
    args = parser.parse_args()

    try:
        page_html = fetch_html(args.url)
    except HTTPError as e:
        print(f"[ERROR] HTTP {e.code}: {e.reason}", file=sys.stderr)
        return 2
    except URLError as e:
        print(f"[ERROR] 网络访问失败: {e.reason}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"[ERROR] 下载页面失败: {e}", file=sys.stderr)
        return 2

    pairs = extract_pairs(page_html)
    if not pairs:
        print(
            "[ERROR] 未提取到词条。可能是页面结构变化、登录/反爬限制，或该环境无法访问 Quizlet。",
            file=sys.stderr,
        )
        return 3

    output = Path(args.output)
    save_pairs(pairs, output, args.format)
    print(f"[OK] 已提取 {len(pairs)} 条词汇 -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
