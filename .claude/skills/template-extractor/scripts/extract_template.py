#!/usr/bin/env python3
"""
raw_sheet_data.json + template.json → history_stats.json 생성 (Phase 1)

LLM이 template.json을 먼저 작성한 후 이 스크립트를 실행합니다.
날짜 파싱, 카테고리 집계, 보상 수치 범위를 자동 계산합니다.

Usage: python extract_template.py
Input:  output/raw_sheet_data.json, output/template.json
Output: output/history_stats.json
"""

import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


# 지원하는 날짜 포맷 (다양한 표기 방식 처리)
DATE_FORMATS = [
    '%Y/%m/%d',
    '%Y.%m.%d',
    '%Y-%m-%d',
    '%m/%d/%Y',
    '%Y/%m/%d %H:%M:%S',
    '%Y.%m.%d %H:%M:%S',
]


def parse_date(value: str) -> datetime | None:
    """여러 포맷으로 날짜 파싱 시도"""
    if not value or not value.strip():
        return None
    v = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    # 슬래시/점 구분자 없이 YYYYMMDD 형식
    m = re.match(r'^(\d{4})(\d{2})(\d{2})$', v)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


def extract_numbers(text: str) -> list[int]:
    """텍스트에서 정수 추출 (보상 수치 파싱용)"""
    return [int(n) for n in re.findall(r'\b\d+\b', text)]


def find_column_index(columns: list[dict], criteria: dict) -> int | None:
    """template.json 열 목록에서 조건에 맞는 첫 열 인덱스 반환"""
    for col in columns:
        match = True
        for key, val in criteria.items():
            if key == 'name_contains':
                if val not in col.get('name', ''):
                    match = False
            elif key == 'type':
                if col.get('type') != val:
                    match = False
            elif col.get(key) != val:
                match = False
        if match:
            return col['index']
    return None


def main() -> int:
    raw_path = Path('output/raw_sheet_data.json')
    template_path = Path('output/template.json')

    if not raw_path.exists():
        print("ERROR: output/raw_sheet_data.json 없음. Phase 1 read_sheet.py 를 먼저 실행하세요.")
        return 1
    if not template_path.exists():
        print("ERROR: output/template.json 없음. LLM이 template.json 을 먼저 생성해야 합니다.")
        return 1

    with open(raw_path, encoding='utf-8') as f:
        raw = json.load(f)
    with open(template_path, encoding='utf-8') as f:
        template = json.load(f)

    rows: list[list[str]] = raw.get('rows', [])
    columns: list[dict] = template.get('columns', [])

    if not rows:
        print("WARNING: 데이터 행이 없습니다. 기본값으로 history_stats.json 생성.")
        _save_defaults()
        return 0

    # 열 인덱스 탐색
    date_col = find_column_index(columns, {'type': 'date'})
    if date_col is None:
        date_col = find_column_index(columns, {'name_contains': '시작'})
    if date_col is None:
        date_col = find_column_index(columns, {'name_contains': '날짜'})

    category_col = find_column_index(columns, {'name_contains': '카테고리'})
    if category_col is None:
        category_col = find_column_index(columns, {'type': 'enum'})

    reward_col = find_column_index(columns, {'name_contains': '보상'})

    # ── 월별 이벤트 수 집계 ──────────────────────────────────────────────
    monthly_counts: dict[str, int] = defaultdict(int)
    unparsed_dates = 0

    if date_col is not None:
        for row in rows:
            if len(row) > date_col:
                dt = parse_date(row[date_col])
                if dt:
                    key = f"{dt.year}-{dt.month:02d}"
                    monthly_counts[key] += 1
                elif row[date_col].strip():
                    unparsed_dates += 1

    if unparsed_dates > 0:
        print(f"WARNING: {unparsed_dates}개 행의 날짜를 파싱하지 못했습니다.")

    counts = list(monthly_counts.values())
    monthly_avg = round(sum(counts) / len(counts)) if counts else 6
    if not counts:
        print("WARNING: 날짜 열을 파싱하지 못해 monthly_avg 를 기본값 6으로 설정합니다.")

    # ── 카테고리 비율 ────────────────────────────────────────────────────
    category_counts: dict[str, int] = defaultdict(int)
    if category_col is not None:
        for row in rows:
            if len(row) > category_col and row[category_col].strip():
                category_counts[row[category_col].strip()] += 1

    total_categorized = sum(category_counts.values())
    category_ratio: dict[str, float] = {}
    if total_categorized > 0:
        for cat, cnt in sorted(category_counts.items()):
            category_ratio[cat] = round(cnt / total_categorized, 2)

    # ── 보상 수치 범위 ───────────────────────────────────────────────────
    reward_range: dict = {"min": None, "max": None, "avg": None, "sample": []}
    if reward_col is not None:
        all_nums: list[int] = []
        samples: list[str] = []
        for row in rows:
            if len(row) > reward_col and row[reward_col].strip():
                val = row[reward_col].strip()
                nums = extract_numbers(val)
                all_nums.extend(nums)
                if val not in samples:
                    samples.append(val)
        if all_nums:
            reward_range = {
                "min": min(all_nums),
                "max": max(all_nums),
                "avg": round(sum(all_nums) / len(all_nums)),
                "sample": samples[:5]  # 예시 5개 보존
            }

    history_stats = {
        "monthly_avg": monthly_avg,
        "monthly_counts": dict(sorted(monthly_counts.items())),
        "category_ratio": category_ratio,
        "reward_range": reward_range,
        "meta": {
            "total_data_rows": len(rows),
            "date_col_index": date_col,
            "category_col_index": category_col,
            "reward_col_index": reward_col,
        }
    }

    output_path = Path('output/history_stats.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(history_stats, f, ensure_ascii=False, indent=2)

    print(f"[Phase 1] 통계 추출 완료")
    print(f"  monthly_avg: {monthly_avg} (월 {min(counts) if counts else '-'}~{max(counts) if counts else '-'}개)")
    print(f"  categories: {list(category_ratio.keys())}")
    print(f"  reward_range: min={reward_range['min']}, max={reward_range['max']}, avg={reward_range['avg']}")
    print(f"  저장: {output_path}")
    return 0


def _save_defaults():
    defaults = {
        "monthly_avg": 6,
        "monthly_counts": {},
        "category_ratio": {},
        "reward_range": {"min": None, "max": None, "avg": None, "sample": []},
        "meta": {"total_data_rows": 0}
    }
    output_path = Path('output/history_stats.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(defaults, f, ensure_ascii=False, indent=2)
    print(f"  기본값으로 저장: {output_path}")


if __name__ == '__main__':
    sys.exit(main())
