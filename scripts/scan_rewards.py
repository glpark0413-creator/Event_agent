#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
보상 명칭·수량 정밀 스캐너

동작:
  - xlsx 전체 날짜형 탭 스캔
  - 각 보상 명칭 셀에 대해 같은 행의 인접 셀에서 수량 탐색
  - 보상 유형별 수량 통계 산출

출력:
  - output/reward_scan_result.json : 보상 명칭↔수량 구조화 데이터 (현재 실행)
"""
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import openpyxl

SOURCE = r"C:\Users\glpark0413\Desktop\업무 자동화-20260521T024618Z-3-001\업무 자동화\실 업무\Event_Agent\Readdocs\[FB_GL] 2026 라이브 이벤트.xlsx"
OUTPUT_DIR = Path("output")
OUTPUT_JSON_DIR = OUTPUT_DIR / "json"

# 보상 명칭 식별 키워드 (구체적 → 일반적 순서)
REWARD_TYPE_MAP = [
    ("픽업팩",   ["픽업팩"]),
    ("선수팩",   ["선수팩", "선수 팩"]),
    ("프리즘다이아", ["프리즘 다이아", "프리즘다이아"]),
    ("다이아",   ["다이아"]),
    ("골드",     ["골드"]),
    ("박스",     ["박스"]),
    ("코인",     ["코인"]),
    ("쿠폰",     ["쿠폰"]),
    ("뽑기",     ["뽑기"]),
    ("팩",       ["팩"]),
]

SKIP_PREFIXES = ("∎", "※", "·", "①", "②", "③", "④", "◆", "▶", "■", "○", "●", "—", "-")

# 수량 패턴 (높은 신뢰도 → 낮은 신뢰도 순)
QTY_PATTERNS = [
    # "50개", "3회", "1장" 등 명확한 단위
    re.compile(r'(\d[\d,]*)\s*(개|회|장|세트|EA|번)(?!\s*[%팩])', re.UNICODE),
    # "다이아 50", "골드 10,000" 등 보상명+수치 (% 또는 팩 직전 숫자 제외)
    re.compile(r'(다이아|골드|코인|포인트)\s*(\d[\d,]+)(?!\s*[%팩])', re.UNICODE),
    # 순수 숫자 (단위 없음) — 낮은 신뢰도
    re.compile(r'^(\d[\d,]+)$'),
]


def is_date_tab(name: str) -> bool:
    return bool(re.match(r'^\d{6}$', str(name)))


def classify_reward_type(text: str) -> str:
    for rtype, keywords in REWARD_TYPE_MAP:
        if any(kw in text for kw in keywords):
            return rtype
    return "기타"


def has_reward_keyword(text: str) -> bool:
    if not text:
        return False
    if any(text.startswith(p) for p in SKIP_PREFIXES):
        return False
    return any(kw in text for _, keywords in REWARD_TYPE_MAP for kw in keywords)


def parse_quantity(text: str) -> dict | None:
    """수량 파싱. 신뢰도(high/low)와 함께 반환."""
    if not text:
        return None
    text = str(text).strip()

    # 높은 신뢰도: 명확한 단위
    m = QTY_PATTERNS[0].search(text)
    if m:
        raw_num = m.group(1).replace(',', '')
        return {"value": int(raw_num), "unit": m.group(2), "raw": m.group(0).strip(), "confidence": "high"}

    # 중간 신뢰도: 보상명+수치 조합
    m = QTY_PATTERNS[1].search(text)
    if m:
        raw_num = m.group(2).replace(',', '')
        return {"value": int(raw_num), "unit": m.group(1), "raw": m.group(0).strip(), "confidence": "medium"}

    # 낮은 신뢰도: 순수 숫자
    m = QTY_PATTERNS[2].match(text)
    if m:
        raw_num = m.group(1).replace(',', '')
        try:
            return {"value": int(raw_num), "unit": "", "raw": raw_num, "confidence": "low"}
        except ValueError:
            pass

    return None


def scan_tab(ws) -> list:
    """
    워크시트 행 단위 스캔.
    보상 명칭 셀을 찾고, 같은 행의 모든 셀에서 수량 탐색.
    인접 컬럼(거리 ≤ 4) 우선, 없으면 행 전체 수량 목록 제공.
    """
    results = []

    for row in ws.iter_rows():
        row_cells = []
        for cell in row:
            if cell.value is not None:
                val = str(cell.value).strip()
                if val:
                    row_cells.append((cell.column, cell.coordinate, val))

        if not row_cells:
            continue

        reward_cells = [
            (col, coord, val) for col, coord, val in row_cells
            if has_reward_keyword(val)
        ]
        if not reward_cells:
            continue

        # 행 내 수량 셀 (보상명 셀 제외)
        qty_cells = []
        for col, coord, val in row_cells:
            if has_reward_keyword(val):
                continue
            qty = parse_quantity(val)
            if qty:
                qty_cells.append({"cell": coord, "col": col, "raw": val, "quantity": qty})

        for col, coord, val in reward_cells:
            rtype = classify_reward_type(val)

            # 같은 셀 내 수량 (예: "다이아 50개")
            self_qty = None
            if re.search(r'\d', val):
                self_qty = parse_quantity(val)

            # 인접 셀 수량 (컬럼 거리 ≤ 4)
            near_qty = None
            if qty_cells:
                by_dist = sorted(qty_cells, key=lambda q: abs(q["col"] - col))
                if by_dist and abs(by_dist[0]["col"] - col) <= 4:
                    near_qty = by_dist[0]

            results.append({
                "cell": coord,
                "reward_name": val,
                "reward_type": rtype,
                "quantity_in_cell": self_qty,
                "nearest_quantity": near_qty,
                "row_all_quantities": qty_cells if qty_cells else [],
            })

    return results


def build_type_summary(tab_results: dict) -> dict:
    """보상 유형별 수량 통계."""
    type_data: dict[str, dict] = {}

    for tab, rows in tab_results.items():
        for item in rows:
            rtype = item["reward_type"]
            if rtype not in type_data:
                type_data[rtype] = {
                    "unique_names": set(),
                    "quantity_values": [],
                    "no_quantity_cells": 0,
                    "source_tabs": set(),
                }

            type_data[rtype]["unique_names"].add(item["reward_name"])
            type_data[rtype]["source_tabs"].add(tab)

            # 수량 수집: 셀 내 > 인접 셀 > 없음
            qty = item.get("quantity_in_cell") or (
                item["nearest_quantity"]["quantity"] if item.get("nearest_quantity") else None
            )
            if qty and qty.get("confidence") in ("high", "medium"):
                type_data[rtype]["quantity_values"].append(qty["value"])
            else:
                type_data[rtype]["no_quantity_cells"] += 1

    summary = {}
    for rtype, data in type_data.items():
        vals = data["quantity_values"]
        summary[rtype] = {
            "unique_names": sorted(data["unique_names"]),
            "quantity_range": {
                "min": min(vals),
                "max": max(vals),
                "avg": round(sum(vals) / len(vals)),
                "samples": len(vals),
            } if vals else None,
            "no_quantity_count": data["no_quantity_cells"],
            "note": "수량 없음 (팩형 보상)" if not vals else "",
            "source_tabs": sorted(data["source_tabs"]),
        }

    return summary


def main(source: str = SOURCE):
    OUTPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_JSON_DIR.mkdir(exist_ok=True)

    print(f"[보상 스캔 시작]")
    print(f"  소스: {source}")

    wb = openpyxl.load_workbook(source, data_only=True)
    date_tabs = [n for n in wb.sheetnames if is_date_tab(n)]
    print(f"  날짜형 탭: {date_tabs}")

    tab_results: dict[str, list] = {}
    for tab in date_tabs:
        rows = scan_tab(wb[tab])
        tab_results[tab] = rows
        qty_found = sum(
            1 for r in rows
            if r.get("quantity_in_cell") or r.get("nearest_quantity")
        )
        print(f"  [{tab}] 보상 셀 {len(rows)}개 (수량 확인: {qty_found}개, 미확인: {len(rows) - qty_found}개)")

    summary = build_type_summary(tab_results)

    result = {
        "scanned_at": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "summary_by_type": summary,
        "per_tab": tab_results,
    }

    out_path = OUTPUT_JSON_DIR / "reward_scan_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n[보상 유형 요약]")
    for rtype, info in summary.items():
        qty_r = info["quantity_range"]
        if qty_r:
            print(f"  {rtype:12s} | {qty_r['min']}~{qty_r['max']} (평균 {qty_r['avg']}) | {len(info['unique_names'])}종")
        else:
            print(f"  {rtype:12s} | 수량 없음 | {len(info['unique_names'])}종")

    print(f"\n저장: {out_path}")


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    src = sys.argv[1] if len(sys.argv) > 1 else SOURCE
    main(src)
