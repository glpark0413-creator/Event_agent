# -*- coding: utf-8 -*-
"""
export_confirmed_to_excel.py

확정된 이벤트 기획안(confirmed_events.json)을 서식이 적용된 xlsx 파일로 내보냅니다.
이벤트 기획 자동화 에이전트 Phase B 산출물 생성 스크립트.
"""

import sys
import io
import os
import json
import argparse
from datetime import datetime
from pathlib import Path

# Windows 환경에서 한국어 출력 보장
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    from openpyxl import Workbook
    from openpyxl.styles import (
        Font, PatternFill, Alignment, Border, Side, numbers
    )
    from openpyxl.utils import get_column_letter
except ImportError:
    print("[오류] openpyxl 패키지가 설치되어 있지 않습니다.", file=sys.stderr)
    print("       설치 명령: pip install openpyxl", file=sys.stderr)
    sys.exit(1)


# ─────────────────────────────────────────────
# 상수 정의
# ─────────────────────────────────────────────

HEADER_BG_COLOR = "1F4E79"      # 짙은 파랑
HEADER_FONT_COLOR = "FFFFFF"    # 흰색
ALT_ROW_COLOR = "F2F2F2"        # 연한 회색 (짝수 행)
WHITE_COLOR = "FFFFFF"          # 흰색 (홀수 행)

DATE_TYPE_KEYWORDS = ("일", "날짜", "date", "dt")
NUMBER_TYPE_KEYWORDS = ("수", "개수", "금액", "포인트", "수치", "number", "num", "count")

MAX_COL_WIDTH = 50  # 최대 열 너비 (글자 수 기준)
MIN_COL_WIDTH = 8   # 최소 열 너비


# ─────────────────────────────────────────────
# 유틸리티 함수
# ─────────────────────────────────────────────

def make_thin_border() -> Border:
    """얇은 테두리 스타일을 반환합니다."""
    thin = Side(style="thin", color="AAAAAA")
    return Border(left=thin, right=thin, top=thin, bottom=thin)


def make_header_fill() -> PatternFill:
    return PatternFill(fill_type="solid", fgColor=HEADER_BG_COLOR)


def make_alt_fill() -> PatternFill:
    return PatternFill(fill_type="solid", fgColor=ALT_ROW_COLOR)


def make_white_fill() -> PatternFill:
    return PatternFill(fill_type="solid", fgColor=WHITE_COLOR)


def is_date_column(col_name: str, col_type: str = "") -> bool:
    """열 이름 또는 타입 기반으로 날짜 열 여부 판단."""
    col_name_lower = col_name.lower()
    col_type_lower = col_type.lower()
    if col_type_lower == "date":
        return True
    return any(kw in col_name_lower for kw in DATE_TYPE_KEYWORDS)


def is_number_column(col_name: str, col_type: str = "") -> bool:
    """열 이름 또는 타입 기반으로 숫자 열 여부 판단."""
    col_name_lower = col_name.lower()
    col_type_lower = col_type.lower()
    if col_type_lower in ("number", "integer", "float"):
        return True
    return any(kw in col_name_lower for kw in NUMBER_TYPE_KEYWORDS)


def calc_col_width(values: list[str], header: str) -> int:
    """헤더와 데이터 값을 기반으로 열 너비를 계산합니다."""
    max_len = len(header)
    for val in values:
        # 한글은 2칸으로 계산 (근사치)
        display_len = sum(2 if ord(c) > 127 else 1 for c in str(val))
        if display_len > max_len:
            max_len = display_len
    return min(max(max_len + 2, MIN_COL_WIDTH), MAX_COL_WIDTH)


def format_target_month_for_filename(target_month: str) -> str:
    """
    target_month (예: '2025-05') 를 파일명용 문자열로 변환.
    '2025-05' → '250500'
    """
    try:
        parts = target_month.split("-")
        year_short = parts[0][2:]  # 4자리 연도 → 2자리
        month = parts[1].zfill(2) if len(parts) > 1 else "00"
        return f"{year_short}{month}00"
    except (IndexError, ValueError):
        return target_month.replace("-", "")


# ─────────────────────────────────────────────
# 메인 로직
# ─────────────────────────────────────────────

def load_confirmed_events(input_path: Path) -> dict:
    """confirmed_events.json 파일을 읽습니다."""
    if not input_path.exists():
        print(f"[오류] 확정 이벤트 파일을 찾을 수 없습니다: {input_path}", file=sys.stderr)
        sys.exit(1)

    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    if "events" not in data:
        print("[오류] confirmed_events.json에 'events' 키가 없습니다.", file=sys.stderr)
        sys.exit(1)

    return data


def load_template(template_path: Path) -> dict | None:
    """template.json 파일을 읽습니다. 파일이 없으면 None 반환."""
    if not template_path.exists():
        return None
    try:
        with open(template_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[경고] template.json 읽기 실패 (무시하고 계속): {e}", file=sys.stderr)
        return None


def derive_columns(events: list[dict], template: dict | None) -> list[dict]:
    """
    events 데이터와 template 정의를 결합해 열 메타데이터 목록을 반환합니다.
    반환 형식: [{"name": str, "type": str, "required": bool}, ...]
    """
    # template에서 열 순서·타입 정보 추출
    template_cols: dict[str, dict] = {}
    template_order: list[str] = []
    if template and "columns" in template:
        for col in template["columns"]:
            name = col.get("name", col.get("original_name", ""))
            if name:
                template_cols[name] = col
                template_order.append(name)

    # 실제 이벤트 데이터에서 등장하는 키 수집 (id, status 제외)
    SKIP_KEYS = {"id", "status"}
    event_keys: list[str] = []
    seen: set[str] = set()
    for ev in events:
        for k in ev.keys():
            if k not in SKIP_KEYS and k not in seen:
                event_keys.append(k)
                seen.add(k)

    # 최종 열 순서: template 순서 우선, 나머지 이벤트 키 추가
    final_order: list[str] = []
    for name in template_order:
        if name in seen:
            final_order.append(name)
    for name in event_keys:
        if name not in final_order:
            final_order.append(name)

    # 열 메타데이터 빌드
    columns = []
    for name in final_order:
        meta = template_cols.get(name, {})
        col_type = meta.get("type", "string")
        required = meta.get("required", False)
        columns.append({
            "name": name,
            "type": col_type,
            "required": required,
        })

    return columns


def build_event_sheet(wb: Workbook, events: list[dict], columns: list[dict]) -> None:
    """'이벤트 목록' 시트를 생성하고 서식을 적용합니다."""
    ws = wb.create_sheet("이벤트 목록", 0)

    border = make_thin_border()
    header_fill = make_header_fill()
    alt_fill = make_alt_fill()
    white_fill = make_white_fill()

    # ── 헤더 행 ──────────────────────────────
    header_font = Font(name="맑은 고딕", bold=True, color=HEADER_FONT_COLOR, size=10)
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    col_names = [c["name"] for c in columns]

    for col_idx, col_meta in enumerate(columns, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_meta["name"])
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = border

    # 자동 필터 적용
    last_col_letter = get_column_letter(len(columns))
    ws.auto_filter.ref = f"A1:{last_col_letter}1"

    # 첫 행 고정
    ws.freeze_panes = "A2"

    # 헤더 행 높이
    ws.row_dimensions[1].height = 22

    # ── 데이터 행 ─────────────────────────────
    data_font = Font(name="맑은 고딕", size=10)

    # 열 너비 계산용 값 수집
    col_values: dict[str, list[str]] = {c["name"]: [] for c in columns}

    for row_idx, event in enumerate(events, start=2):
        is_even_row = (row_idx % 2 == 0)
        row_fill = alt_fill if is_even_row else white_fill

        for col_idx, col_meta in enumerate(columns, start=1):
            col_name = col_meta["name"]
            col_type = col_meta["type"]
            raw_value = event.get(col_name, "")

            # 타입별 값 처리 및 정렬
            if is_number_column(col_name, col_type):
                # 숫자 열: 우측 정렬
                try:
                    display_value = int(raw_value) if str(raw_value).isdigit() else raw_value
                except (ValueError, TypeError):
                    display_value = raw_value
                alignment = Alignment(horizontal="right", vertical="center")
            elif is_date_column(col_name, col_type):
                # 날짜 열: 가운데 정렬
                display_value = raw_value
                alignment = Alignment(horizontal="center", vertical="center")
            else:
                # 텍스트 열: 좌측 정렬
                display_value = raw_value
                alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

            cell = ws.cell(row=row_idx, column=col_idx, value=display_value)
            cell.font = data_font
            cell.fill = row_fill
            cell.alignment = alignment
            cell.border = border

            col_values[col_name].append(str(raw_value) if raw_value is not None else "")

        # 행 높이 (텍스트 줄바꿈 고려해 기본 18pt)
        ws.row_dimensions[row_idx].height = 18

    # ── 열 너비 자동 조정 ─────────────────────
    for col_idx, col_meta in enumerate(columns, start=1):
        col_name = col_meta["name"]
        width = calc_col_width(col_values.get(col_name, []), col_name)
        ws.column_dimensions[get_column_letter(col_idx)].width = width


def build_meta_sheet(wb: Workbook, data: dict, output_path: Path) -> None:
    """'메타정보' 시트를 생성합니다."""
    ws = wb.create_sheet("메타정보")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    events = data.get("events", [])
    confirmed_count = sum(1 for e in events if e.get("status") == "confirmed")

    meta_rows = [
        ("항목", "값"),
        ("생성일시", now_str),
        ("장르", data.get("genre", "")),
        ("타겟마켓", data.get("market", "")),
        ("대상연월", data.get("target_month", "")),
        ("전체 이벤트 수", len(events)),
        ("확정 이벤트 수", confirmed_count),
        ("출력 파일", str(output_path.name)),
    ]

    border = make_thin_border()
    header_fill = make_header_fill()
    header_font = Font(name="맑은 고딕", bold=True, color=HEADER_FONT_COLOR, size=10)
    label_font = Font(name="맑은 고딕", bold=True, size=10)
    value_font = Font(name="맑은 고딕", size=10)

    for row_idx, (label, value) in enumerate(meta_rows, start=1):
        label_cell = ws.cell(row=row_idx, column=1, value=label)
        value_cell = ws.cell(row=row_idx, column=2, value=value)

        label_cell.border = border
        value_cell.border = border
        label_cell.alignment = Alignment(horizontal="center", vertical="center")
        value_cell.alignment = Alignment(horizontal="left", vertical="center")

        if row_idx == 1:
            label_cell.font = header_font
            label_cell.fill = header_fill
            value_cell.font = header_font
            value_cell.fill = header_fill
        else:
            label_cell.font = label_font
            value_cell.font = value_font

        ws.row_dimensions[row_idx].height = 18

    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["B"].width = 40
    ws.freeze_panes = "A2"


def save_export_result(result_path: Path, file_path: Path, data: dict) -> None:
    """내보내기 결과를 last_excel_export.json에 저장합니다."""
    events = data.get("events", [])
    result = {
        "file_path": str(file_path),
        "event_count": len(events),
        "target_month": data.get("target_month", ""),
        "exported_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


def export_to_excel(
    input_path: Path,
    template_path: Path,
    output_dir: Path,
    output_override: Path | None = None,
) -> Path:
    """
    메인 내보내기 함수.
    Returns: 생성된 xlsx 파일 경로
    """
    # 1. 데이터 로드
    print("확정 이벤트 데이터를 읽는 중...", flush=True)
    data = load_confirmed_events(input_path)
    template = load_template(template_path)

    events = data.get("events", [])
    if not events:
        print("[경고] 이벤트가 없습니다. 빈 파일을 생성합니다.", file=sys.stderr)

    # 2. 열 메타데이터 결정
    columns = derive_columns(events, template)
    if not columns:
        print("[오류] 열 정의를 추출할 수 없습니다.", file=sys.stderr)
        sys.exit(1)

    # 3. 출력 파일 경로 결정
    output_file_dir = output_dir / "file"
    output_json_dir = output_dir / "json"
    output_file_dir.mkdir(parents=True, exist_ok=True)
    output_json_dir.mkdir(parents=True, exist_ok=True)

    if output_override:
        output_path = output_override
    else:
        target_month = data.get("target_month", "unknown")
        month_str = format_target_month_for_filename(target_month)
        timestamp = datetime.now().strftime("%H%M%S")
        filename = f"이벤트기획_{month_str}_{timestamp}.xlsx"
        output_path = output_file_dir / filename

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 4. 워크북 생성
    print("Excel 파일을 생성하는 중...", flush=True)
    wb = Workbook()

    # 기본 시트 제거 (openpyxl이 자동 생성)
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]

    # 5. 시트 구성
    build_event_sheet(wb, events, columns)
    build_meta_sheet(wb, data, output_path)

    # 6. 파일 저장
    wb.save(output_path)
    print(f"저장 완료: {output_path}", flush=True)

    # 7. 결과 메타데이터 저장
    result_path = output_dir / "json" / "last_excel_export.json"
    save_export_result(result_path, output_path, data)

    return output_path


def print_completion_summary(output_path: Path, data: dict) -> None:
    """완료 메시지를 한국어로 출력합니다."""
    events = data.get("events", [])
    confirmed = sum(1 for e in events if e.get("status") == "confirmed")
    target_month = data.get("target_month", "")
    genre = data.get("genre", "")
    market = data.get("market", "")

    print()
    print("=" * 55)
    print("  이벤트 기획안 Excel 내보내기 완료")
    print("=" * 55)
    print(f"  출력 파일  : {output_path.name}")
    print(f"  저장 경로  : {output_path.parent}")
    print(f"  대상 연월  : {target_month}")
    print(f"  장르       : {genre}")
    print(f"  타겟 마켓  : {market}")
    print(f"  이벤트 수  : {confirmed} / {len(events)}개 확정")
    print("=" * 55)
    print()


# ─────────────────────────────────────────────
# CLI 진입점
# ─────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="확정된 이벤트 기획안을 Excel(.xlsx) 파일로 내보냅니다.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python export_confirmed_to_excel.py
  python export_confirmed_to_excel.py --input output/confirmed_events.json
  python export_confirmed_to_excel.py --output output/my_events.xlsx
        """,
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="입력 JSON 파일 경로 (기본값: output/confirmed_events.json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="출력 xlsx 파일 경로 (기본값: output/이벤트기획_{연월}_{시각}.xlsx)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # 스크립트 위치 기준으로 프로젝트 루트 결정
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    output_dir = project_root / "output"

    # 입력 파일 경로 결정
    input_path = args.input if args.input else output_dir / "json" / "confirmed_events.json"
    template_path = output_dir / "json" / "template.json"

    # 입력 파일 절대 경로화
    if not input_path.is_absolute():
        input_path = Path.cwd() / input_path
    if not template_path.is_absolute():
        template_path = Path.cwd() / template_path

    print(f"입력 파일: {input_path}")
    if template_path.exists():
        print(f"템플릿 파일: {template_path}")
    else:
        print("템플릿 파일 없음 — 이벤트 데이터에서 열 구조를 자동 추론합니다.")

    # 출력 경로 절대 경로화
    output_override = None
    if args.output:
        output_override = args.output if args.output.is_absolute() else Path.cwd() / args.output

    try:
        # 데이터 로드 (summary 출력용)
        data = load_confirmed_events(input_path)

        # Excel 내보내기 실행
        output_path = export_to_excel(
            input_path=input_path,
            template_path=template_path,
            output_dir=output_dir,
            output_override=output_override,
        )

        # 완료 메시지 출력
        print_completion_summary(output_path, data)

    except SystemExit:
        raise
    except KeyboardInterrupt:
        print("\n[중단] 사용자에 의해 작업이 취소되었습니다.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[오류] 예기치 않은 오류가 발생했습니다: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
