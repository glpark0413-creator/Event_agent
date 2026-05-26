#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M4_GL 이벤트 엑셀 내보내기 스크립트

동작:
  1. 소스 xlsx의 참조 시트를 복사
  2. 업데이트 주차별 변경 사항 반영 (수렵·오셰르·14일 출석 날짜/이름 갱신)
  3. output/ 폴더에 새 xlsx 저장

사용:
  # 기본 (6/23 2주차 기준)
  python scripts/export_m4gl_to_excel.py

  # 옵션 지정
  python scripts/export_m4gl_to_excel.py --update-date 260623 --concept "비천의 여름바람" --hunting 용 --week 2
"""

import argparse
import copy
import io
import sys
from datetime import date
from pathlib import Path

import openpyxl
from openpyxl.utils import get_column_letter

# ─── 경로 설정 ────────────────────────────────────────────────────────────────
SOURCE_M4GL = (
    r"C:\Users\glpark0413\Desktop\업무 자동화-20260521T024618Z-3-001"
    r"\업무 자동화\실 업무\Event_Agent\Readdocs\[M4_GL] 라이브 이벤트.xlsx"
)
OUTPUT_DIR = Path("output")
OUTPUT_FILE_DIR = OUTPUT_DIR / "file"

# ─── 기본 설정: 26.6.23 2주차 ────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "update_date": "260623",
    "concept_kr": "비천의 여름바람 2주차",
    "concept_en": "Bicheon's Summer Breeze - Week 2",
    "hunting_type": "용",           # "흑룡" | "용" (청룡+백룡)
    "week": 2,
    "ref_sheet_summer": "예정 26.6.9 여름바람",   # 14일 출석 / 오셰르 참조
    "ref_sheet_hunting": "종료 26.4.14 봄기운",   # 용의 선물상자 구조 참조
    # ── 14일 출석 변경 ───────────────────────────────────────────────
    "attendance": {
        "section_title_row": 37,
        "new_section_title": "1. 한여름의 비천 14일 출석",
        "period_row": 39,
        "new_period": (
            "∎ 진행 기간 :  2026년 6월 23일 업데이트 후"
            " ~ 2026년 7월 6일 23:59 까지 (UTC+8)"
        ),
    },
    # ── 수렵 섹션 날짜 치환 (청룡+백룡) ──────────────────────────────
    # 주의: 긴 문자열 치환이 먼저 적용돼야 부분 치환으로 인한 미스매치를 방지
    "hunting_dates": {
        # ① 봄기운 진행기간 전체 줄 (C56) — 반드시 개별 치환보다 앞에 위치
        "2026년 4월 14일 업데이트 후 ~ 4월 27일 23:59까지 (UTC+8)": (
            "2026년 6월 23일 업데이트 후 ~ 2026년 7월 6일 23:59 까지 (UTC+8)"
        ),
        # ② 개별 날짜 치환 (아이템 행의 획득가능시간·종료일 셀)
        "4월 14일 업데이트 후":  "6월 23일 업데이트 후",
        "4월 20일 23:59:00까지": "6월 29일 23:59:00까지",
        "4월 21일 0시":          "6월 30일 0시",
        "4월 27일  23:59까지":   "7월 6일 23:59까지",   # 이중 공백 버전
        "4월 27일 23:59까지":    "7월 6일 23:59까지",   # 단일 공백 버전
    },
    # ── 수렵 기간 셀(C56) 직접 지정값 (치환 후 덮어씀으로써 확실히 보정) ──
    "hunting_period_cell": "C56",
    "hunting_period_value": (
        "∎ 진행 기간 : 2026년 6월 23일 업데이트 후 ~ 2026년 7월 6일 23:59 까지 (UTC+8)"
        "\n  ┌ 청룡의 선물상자 : 6월 23일 업데이트 후 ~ 6월 29일 23:59 까지 (UTC+8)"
        "\n  └ 백룡의 선물상자 : 6월 30일 0시 ~ 7월 6일 23:59 까지 (UTC+8)"
    ),
    # ── 오셰르 섹션 (폐관수련 → 정령 성장 업) ─────────────────────────
    "osher": {
        "title_row": 105,           # C105 "3. 오셰르의 운수대통"
        "buff_title_row": 107,      # C107 변경 대상
        "period_row": 109,          # C109 변경 대상
        "desc1_row": 111,           # C111 진행방식 설명 1
        "desc2_row": 112,           # C112 진행방식 설명 2 (제거)
        "stat_header_row": 111,     # K111~L111 분류/변경수치 헤더
        "stat_row1": 112,           # K112~L112 → 정령석 소환권 비용 / 0.7
        "stat_row2": 113,           # K113~L113 → 제거
        "table_header_row": 115,    # D115~ 테이블 헤더
        "table_data_start": 117,    # D117~ 테이블 데이터 시작
        "table_data_end": 126,      # 기존 테이블 마지막 행
        # 새 값
        "new_buff_title": "■  정령 성장 업",
        "new_period": (
            "∎ 진행 기간 : 2026년 6월 23일 업데이트 후"
            " ~ 7월 7일 업데이트 전 까지 (UTC+8)"
        ),
        "new_desc1": "- 이벤트 기간동안 정령 성장에 필요한 정령석 소환권 비용이 30% 하락",
        "new_stat_k1": "분류",          "new_stat_l1": "변경 수치",
        "new_stat_k2": "정령석 소환권 비용",  "new_stat_l2": "0.7",
        # 새 테이블 헤더
        "new_table_header": {
            "D": "정령 성장 단계",
            "E": "기존 비용 (정령석 소환권)",
            "F": "이벤트 비용 (정령석 소환권)",
        },
        # 새 테이블 데이터
        "new_table_data": [
            {"D": "1단계",   "E": "(확인 필요)", "F": "(기존 × 0.7)"},
            {"D": "2단계",   "E": "(확인 필요)", "F": "(기존 × 0.7)"},
            {"D": "3단계",   "E": "(확인 필요)", "F": "(기존 × 0.7)"},
            {"D": "4단계",   "E": "(확인 필요)", "F": "(기존 × 0.7)"},
            {"D": "5단계 이상", "E": "(확인 필요)", "F": "(기존 × 0.7)"},
        ],
        # 기존 테이블에서 지울 열 (G~L, 폐관수련 전용 컬럼)
        "cols_to_clear_in_table": ["G", "H", "I", "J", "K", "L"],
    },
    # ── 상단 제목 ──────────────────────────────────────────────────────
    "title_cell": "C1",
    "new_title": "M4/GL _ 6.23 _ Bicheon's Summer Breeze - Week 2 (비천의 여름 바람 2주차)",
}


# ─── 유틸 ─────────────────────────────────────────────────────────────────────

def safe_set(ws, cell_coord: str, value) -> None:
    """병합 셀 최상단 셀만 값 변경; 일반 셀은 직접 변경."""
    cell = ws[cell_coord]
    # 병합 영역 소속 여부 확인
    for merged in ws.merged_cells.ranges:
        min_r, min_c = merged.min_row, merged.min_col
        max_r, max_c = merged.max_row, merged.max_col
        col_idx = cell.column
        if (min_r <= cell.row <= max_r) and (min_c <= col_idx <= max_c):
            # 최상단-최좌측 셀에만 쓰기
            top_left = ws.cell(row=min_r, column=min_c)
            top_left.value = value
            return
    cell.value = value


def clear_row_range(ws, row_start: int, row_end: int,
                    col_start: str = "B", col_end: str = "N") -> None:
    """지정 행 범위의 셀 값만 지운다 (서식 유지)."""
    col_s = openpyxl.utils.column_index_from_string(col_start)
    col_e = openpyxl.utils.column_index_from_string(col_end)
    for row in range(row_start, row_end + 1):
        for col in range(col_s, col_e + 1):
            ws.cell(row=row, column=col).value = None


def replace_text_in_ws(ws, replacements: dict) -> int:
    """시트 전체 문자열 셀에서 지정 텍스트를 치환. 변경 수 반환."""
    count = 0
    for row in ws.iter_rows():
        for cell in row:
            if isinstance(cell.value, str):
                for old, new in replacements.items():
                    if old in cell.value:
                        cell.value = cell.value.replace(old, new)
                        count += 1
    return count


def copy_rows_from_ws(src_ws, dst_ws,
                      src_start: int, src_end: int,
                      dst_start: int,
                      col_start: str = "B", col_end: str = "N") -> None:
    """src_ws 의 src_start~src_end 행을 dst_ws 의 dst_start 부터 복사."""
    col_s = openpyxl.utils.column_index_from_string(col_start)
    col_e = openpyxl.utils.column_index_from_string(col_end)
    offset = dst_start - src_start
    for row in range(src_start, src_end + 1):
        dst_row = row + offset
        for col in range(col_s, col_e + 1):
            src_cell = src_ws.cell(row=row, column=col)
            dst_cell = dst_ws.cell(row=dst_row, column=col)
            dst_cell.value = src_cell.value


# ─── 핵심 처리 ────────────────────────────────────────────────────────────────

def apply_attendance_update(ws, cfg: dict) -> None:
    """14일 출석 이벤트 이름 / 기간 갱신."""
    att = cfg["attendance"]
    safe_set(ws, f"C{att['section_title_row']}", att["new_section_title"])
    safe_set(ws, f"C{att['period_row']}", att["new_period"])
    print(f"  [출석] C{att['section_title_row']} → {att['new_section_title']}")
    print(f"  [출석] C{att['period_row']} → (6/23 기간 갱신)")


def apply_hunting_update(ws, ref_wb, cfg: dict) -> None:
    """
    수렵 섹션 교체:
      - hunting_type == "용": 봄기운 용의 선물상자 구조 복사 + 날짜 치환
      - hunting_type == "흑룡": 날짜 문자열만 치환
    """
    if cfg["hunting_type"] != "용":
        cnt = replace_text_in_ws(ws, cfg.get("hunting_dates_heukryong", {}))
        print(f"  [수렵-흑룡] 날짜 치환 {cnt}건")
        return

    ref_sheet = cfg["ref_sheet_hunting"]
    ref_ws = ref_wb[ref_sheet]

    # 봄기운 시트의 수렵 범위: row 54~100
    SRC_HUNT_START, SRC_HUNT_END = 54, 100
    # 여름바람 시트의 수렵 범위: row 54~103
    DST_HUNT_START, DST_HUNT_END = 54, 103

    print(f"  [수렵-용] '{ref_sheet}' row {SRC_HUNT_START}~{SRC_HUNT_END} 복사 → row {DST_HUNT_START}~")

    # 기존 내용 지우기
    clear_row_range(ws, DST_HUNT_START, DST_HUNT_END)

    # 봄기운 행 복사
    copy_rows_from_ws(ref_ws, ws,
                      src_start=SRC_HUNT_START, src_end=SRC_HUNT_END,
                      dst_start=DST_HUNT_START,
                      col_start="C", col_end="M")

    # 날짜 문자열 치환 (봄기운 4월 날짜 → 6월 날짜)
    cnt = replace_text_in_ws(ws, cfg["hunting_dates"])
    print(f"  [수렵-용] 날짜 치환 {cnt}건")

    # C56 기간 셀 직접 덮어쓰기 (복잡한 다줄 텍스트는 치환보다 직접 지정이 안전)
    period_cell = cfg.get("hunting_period_cell", "C56")
    period_val  = cfg.get("hunting_period_value")
    if period_val:
        safe_set(ws, period_cell, period_val)
        print(f"  [수렵-용] {period_cell} 기간 직접 지정 완료")


def apply_osher_update(ws, cfg: dict) -> None:
    """오셰르 섹션 갱신 (폐관수련 업 → 정령 성장 업)."""
    osher = cfg["osher"]

    # 버프 타이틀 변경
    safe_set(ws, f"C{osher['buff_title_row']}", osher["new_buff_title"])

    # 기간 변경
    safe_set(ws, f"C{osher['period_row']}", osher["new_period"])

    # 진행방식 설명 변경
    safe_set(ws, f"C{osher['desc1_row']}", osher["new_desc1"])
    # desc2 행 비우기
    ws.cell(row=osher["desc2_row"], column=3).value = None

    # 분류/변경수치 통계 헤더/값 갱신
    safe_set(ws, f"K{osher['stat_header_row']}", osher["new_stat_k1"])
    safe_set(ws, f"L{osher['stat_header_row']}", osher["new_stat_l1"])
    safe_set(ws, f"K{osher['stat_row1']}", osher["new_stat_k2"])
    safe_set(ws, f"L{osher['stat_row1']}", osher["new_stat_l2"])
    # stat_row2 제거
    ws.cell(row=osher["stat_row2"], column=11).value = None
    ws.cell(row=osher["stat_row2"], column=12).value = None

    # 기존 테이블 지우기 (row 115 헤더 + 116 + 117~126 데이터)
    clear_row_range(ws, osher["table_header_row"], osher["table_data_end"],
                    col_start="D", col_end="L")

    # 새 테이블 헤더 쓰기
    for col_letter, val in osher["new_table_header"].items():
        col_idx = openpyxl.utils.column_index_from_string(col_letter)
        ws.cell(row=osher["table_header_row"], column=col_idx).value = val

    # 새 테이블 데이터 쓰기
    for i, row_data in enumerate(osher["new_table_data"]):
        row_num = osher["table_data_start"] + i
        for col_letter, val in row_data.items():
            col_idx = openpyxl.utils.column_index_from_string(col_letter)
            ws.cell(row=row_num, column=col_idx).value = val

    # 비고 추가
    note_row = osher["table_data_start"] + len(osher["new_table_data"]) + 1
    ws.cell(row=note_row, column=3).value = (
        "※ 정령 성장 단계별 기본 비용 수치는 게임 데이터 확인 후 기입 필요"
    )

    print(f"  [오셰르] C{osher['buff_title_row']} → {osher['new_buff_title']}")
    print(f"  [오셰르] 테이블 갱신 완료 (단계별 비용 확인 필요 표시)")


def apply_title_update(ws, cfg: dict) -> None:
    """시트 제목(C1) 갱신."""
    safe_set(ws, cfg["title_cell"], cfg["new_title"])
    print(f"  [제목] {cfg['title_cell']} → {cfg['new_title'][:60]}...")


# ─── 메인 ─────────────────────────────────────────────────────────────────────

def main(cfg: dict = None) -> Path:
    if cfg is None:
        cfg = DEFAULT_CONFIG

    OUTPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_FILE_DIR.mkdir(exist_ok=True)

    print(f"[M4_GL 이벤트 엑셀 내보내기]")
    print(f"  업데이트 날짜 : {cfg['update_date']}")
    print(f"  컨셉         : {cfg['concept_kr']}")
    print(f"  참조 시트    : {cfg['ref_sheet_summer']}")
    print(f"  수렵 유형    : {cfg['hunting_type']}")

    # ① 소스 파일 로드
    print(f"\n소스 파일 로드: {SOURCE_M4GL}")
    wb_src = openpyxl.load_workbook(SOURCE_M4GL, data_only=True)

    # 수렵 참조 파일도 같은 워크북 (봄기운 시트가 동일 파일 내)
    wb_ref_hunting = wb_src  # 같은 파일

    # ② 참조 시트 복사
    ref_ws = wb_src[cfg["ref_sheet_summer"]]
    new_ws = wb_src.copy_worksheet(ref_ws)
    new_ws.title = f"예정 26.{cfg['update_date'][2:4]}.{cfg['update_date'][4:6]} {cfg['concept_kr']}"
    print(f"  새 시트 생성 : '{new_ws.title}'")

    # ③ 각 섹션 갱신
    print("\n[섹션 갱신 시작]")
    apply_title_update(new_ws, cfg)
    apply_attendance_update(new_ws, cfg)

    if cfg["hunting_type"] == "용":
        apply_hunting_update(new_ws, wb_ref_hunting, cfg)
    else:
        apply_hunting_update(new_ws, wb_ref_hunting, cfg)

    apply_osher_update(new_ws, cfg)

    # ④ 출력 파일 저장
    yyyymm = f"26{cfg['update_date'][2:4]}{cfg['update_date'][4:6]}"
    out_filename = f"M4GL_이벤트기획_{yyyymm}.xlsx"
    out_path = OUTPUT_FILE_DIR / out_filename
    wb_src.save(str(out_path))
    print(f"\n[완료] 저장: {out_path}")
    return out_path


# ─── CLI 진입점 ───────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(description="M4_GL 이벤트 엑셀 내보내기")
    parser.add_argument("--update-date", default="260623",
                        help="업데이트 날짜 YYMMDD (기본: 260623)")
    parser.add_argument("--concept", default="비천의 여름바람 2주차",
                        help="이벤트 컨셉명 (한국어)")
    parser.add_argument("--hunting", default="용",
                        choices=["흑룡", "용"],
                        help="수렵 이벤트 유형 (기본: 용)")
    parser.add_argument("--week", type=int, default=2,
                        help="주차 (기본: 2)")
    return parser.parse_args()


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    args = parse_args()

    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg["update_date"] = args.update_date
    cfg["concept_kr"] = args.concept
    cfg["hunting_type"] = args.hunting
    cfg["week"] = args.week

    out = main(cfg)
    print(f"\n엑셀 파일: {out.resolve()}")
