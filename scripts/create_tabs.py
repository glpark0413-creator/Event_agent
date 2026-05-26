#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
이벤트 시트 탭 생성 스크립트 — NC_KR (나이트 크로우)
- 날짜/헤더 자동 갱신 (한국어 날짜 텍스트 + datetime 셀)
- datetime 셀 직접 갱신 (date_map 사용)
- output/json/event_names_config.json 이 있으면 이벤트 명칭 자동 치환
- 시즌·월 키워드 포함 셀 경고 출력
"""
import io
import json
import sys
from pathlib import Path
from datetime import datetime, date
import openpyxl

SOURCE = r"C:\Users\glpark0413\Desktop\업무 자동화-20260521T024618Z-3-001\업무 자동화\실 업무\Event_Agent\Readdocs\projects\FB_GL_1WrTrDgP.xlsx"

import sys as _sys_ct
_sys_ct.path.insert(0, str(Path(__file__).resolve().parent))
from _project_config import load_project_paths as _load_paths_ct
_paths_ct = _load_paths_ct()

OUTPUT_DIR = Path("output")
OUTPUT_FILE_DIR = _paths_ct.file_dir if _paths_ct else Path("output") / "file"
OUTPUT_JSON_DIR = _paths_ct.work_dir if _paths_ct else Path("output") / "json"
OUTPUT_FILE = OUTPUT_FILE_DIR / "이벤트기획_260611_260618.xlsx"
EVENT_NAMES_CONFIG = OUTPUT_JSON_DIR / "event_names_config.json"

# 시즌·월 키워드: 이 단어가 포함된 셀은 수동 검토 권장
SEASON_KEYWORDS = [
    "봄의", "여름의", "가을의", "겨울의",
    "황금의", "축제의", "기념",
    "1월의", "2월의", "3월의", "4월의", "5월의",
    "6월의", "7월의", "8월의", "9월의", "10월의", "11월의", "12월의",
    "얼리썸머", "초여름", "쿨 서머", "5월의",
]

# 각 탭별 설정 — FB_GL 날짜 치환 규칙
# 260611 (260528 참조, +14일 시프트): 2026-06-11 이벤트 주차 생성 (14일 주기 메인 탭)
# 260618 (260604 참조, +14일 시프트): 2026-06-18 이벤트 주차 생성 (7일 주기 포인트레이스/빙고 탭)
UPDATES = {
    "260611": {
        "source_tab": "260528",
        # datetime 셀용 직접 매핑 (MM/DD → MM/DD), +14일
        # 출석 이벤트 날짜 셀(C13~C26): 05/28~06/10 → 06/11~06/24
        "date_map": {
            "05/28": "06/11",
            "05/29": "06/12",
            "05/30": "06/13",
            "05/31": "06/14",
            "06/01": "06/15",
            "06/02": "06/16",
            "06/03": "06/17",
            "06/04": "06/18",
            "06/05": "06/19",
            "06/06": "06/20",
            "06/07": "06/21",
            "06/08": "06/22",
            "06/09": "06/23",
            "06/10": "06/24",
            "06/11": "06/25",
        },
        # 문자열 셀용 치환 규칙 (순서 중요 — 긴 패턴 먼저)
        "replacements": [
            # 헤더 (B3)
            ("05.28_ Event", "06.11_ Event"),
            # 출석 이벤트 기간 (수요일 종료)
            ("05/28(목) 09:00 ~ 06/10(수) 23:59", "06/11(목) 09:00 ~ 06/24(수) 23:59"),
            # 응모권 이벤트 기간 (14일 명시)
            ("05/28(목) 09:00 ~ 06/11(목) 08:59:59 (14일)", "06/11(목) 09:00 ~ 06/25(목) 08:59:59 (14일)"),
            # 교환소 이벤트 기간 (초 없음)
            ("05/28(목) 09:00 ~ 06/11(목) 08:59", "06/11(목) 09:00 ~ 06/25(목) 08:59"),
            # PvP 핫타임 (상시)
            ("05/28(목) 09:00 ~ 상시", "06/11(목) 09:00 ~ 상시"),
            # 타이어끌기·야구공찾기·승부예측 (초 있음)
            ("05/28(목) 09:00 ~ 06/11(목) 08:59:59", "06/11(목) 09:00 ~ 06/25(목) 08:59:59"),
            # 나머지 05/28(목) 패턴 (위 규칙에서 처리 안 된 경우)
            ("05/28(목)", "06/11(목)"),
        ],
        "event_name_replacements": [],
    },
    "260618": {
        "source_tab": "260604",
        # datetime 셀용 직접 매핑 (MM/DD → MM/DD), +14일
        # 260604 탭은 주로 텍스트 기간 표기 사용 (datetime 셀 드물지만 안전하게 포함)
        "date_map": {
            "06/04": "06/18",
            "06/05": "06/19",
            "06/06": "06/20",
            "06/07": "06/21",
            "06/08": "06/22",
            "06/09": "06/23",
            "06/10": "06/24",
            "06/11": "06/25",
        },
        # 문자열 셀용 치환 규칙 (순서 중요 — 긴 패턴 먼저)
        "replacements": [
            # 헤더 (B3)
            ("06.04_ Event", "06.18_ Event"),
            # 포인트 레이스 기간 (7일간 진행)
            ("06/04(목) 09:00 ~ 06/11(목) 08:59 (7일간 진행)", "06/18(목) 09:00 ~ 06/25(목) 08:59 (7일간 진행)"),
            # 룰렛·빙고 기간 (공백 포함 "06/04 (목)" 형식)
            ("06/04 (목) 09:00 ~ 06/11(목) 08:59:59", "06/18(목) 09:00 ~ 06/25(목) 08:59:59"),
            # 나머지 "06/04 (목)" (공백 있는 형식)
            ("06/04 (목)", "06/18(목)"),
            # 나머지 "06/04(목)" (공백 없는 형식)
            ("06/04(목)", "06/18(목)"),
            # 나머지 "06/11(목)" (이미 위에서 처리 안 된 경우)
            ("06/11(목)", "06/25(목)"),
        ],
        "event_name_replacements": [],
    },
}


def load_event_names_config():
    """
    output/event_names_config.json 이 존재하면 로드해서 탭별 이벤트 명칭 치환 목록 반환.
    Claude가 장르·시즌 분석 후 미리 생성해두는 파일.

    반환 형식:
    {
      "260611": [("구이름", "새이름"), ...],
      "260618": []
    }
    """
    if not EVENT_NAMES_CONFIG.exists():
        return {}
    with open(EVENT_NAMES_CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)

    genre = cfg.get("genre", "")
    target_month = cfg.get("target_month", "")
    genre_phrases = cfg.get("genre_phrases", [])
    raw = cfg.get("event_name_replacements", {})

    if genre or target_month:
        print(f"  [config] 장르={genre}, 대상월={target_month}")
    if genre_phrases:
        print(f"  [config] 장르 키워드: {', '.join(genre_phrases[:8])}")

    return {tab: [tuple(r) for r in repls] for tab, repls in raw.items()}


def apply_replacements(ws, replacements, date_map=None, event_name_replacements=None):
    """
    워크시트 전체 셀에 치환 적용.
    - datetime/date 객체: date_map으로 직접 날짜 갱신 (마커 트릭 없이 안전하게 처리)
    - str: replacements → event_name_replacements 순서로 적용
    """
    changed = []
    all_str_replacements = list(replacements) + list(event_name_replacements or [])

    for row in ws.iter_rows():
        for cell in row:
            if cell.value is None:
                continue

            # datetime / date 객체: date_map으로 직접 매핑
            if isinstance(cell.value, (datetime, date)):
                if not date_map:
                    continue
                old_date = cell.value
                mmdd = old_date.strftime("%m/%d")
                if mmdd not in date_map:
                    continue
                new_mmdd = date_map[mmdd]
                month, day = map(int, new_mmdd.split("/"))
                year = old_date.year
                if isinstance(old_date, datetime):
                    new_date = datetime(year, month, day,
                                        old_date.hour, old_date.minute, old_date.second)
                else:
                    new_date = date(year, month, day)
                changed.append((cell.coordinate, str(old_date), str(new_date)))
                cell.value = new_date
                continue

            if not isinstance(cell.value, str):
                continue

            new_val = cell.value
            for old, new in all_str_replacements:
                new_val = new_val.replace(old, new)
            if new_val != cell.value:
                changed.append((cell.coordinate, cell.value, new_val))
                cell.value = new_val

    return changed


def _safe_print(text: str) -> None:
    """cp949 인코딩 불가 문자를 '?'로 대체하여 출력."""
    print(text.encode("cp949", errors="replace").decode("cp949"))


def warn_season_keywords(ws, tab_name):
    """시즌·월 키워드가 남아있는 셀을 경고로 출력. 반환값은 (coord, val) 리스트."""
    hits = []
    for row in ws.iter_rows():
        for cell in row:
            if not cell.value or not isinstance(cell.value, str):
                continue
            for kw in SEASON_KEYWORDS:
                if kw in cell.value:
                    hits.append((cell.coordinate, cell.value[:100]))
                    break
    if hits:
        _safe_print(f"\n  [경고] [{tab_name}] 시즌·월 키워드 포함 셀 - 이벤트 명칭 확인 권장:")
        for coord, val in hits:
            _safe_print(f"       {coord}: '{val}'")
    return hits


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_FILE_DIR.mkdir(exist_ok=True)
    OUTPUT_JSON_DIR.mkdir(exist_ok=True)

    print("[작업 시작]")
    print(f"  소스: {SOURCE}")

    # event_names_config.json 로드 (Claude가 생성해둔 경우)
    event_name_cfg = load_event_names_config()
    if event_name_cfg:
        print(f"  이벤트 명칭 config 적용: {list(event_name_cfg.keys())} 탭")
        for tab_name, repls in event_name_cfg.items():
            if tab_name in UPDATES:
                UPDATES[tab_name]["event_name_replacements"] = repls
    else:
        print("  event_names_config.json 없음 - 이벤트 명칭은 날짜/패턴 치환만 적용")

    print("  파일 로드 중...")
    wb = openpyxl.load_workbook(SOURCE)

    # 필요한 소스 탭만 남기기
    sheets_needed = {cfg["source_tab"] for cfg in UPDATES.values()}
    for name in list(wb.sheetnames):
        if name not in sheets_needed:
            wb.remove(wb[name])
    print(f"  남은 시트: {wb.sheetnames}")

    all_changes = {}
    all_season_warnings = {}

    for new_tab, cfg in UPDATES.items():
        src = cfg["source_tab"]
        if src not in wb.sheetnames:
            print(f"\n  [SKIP] 소스 탭 '{src}' 없음 → {new_tab} 건너뜀")
            continue

        ws = wb[src]
        changes = apply_replacements(
            ws,
            cfg["replacements"],
            date_map=cfg.get("date_map"),
            event_name_replacements=cfg.get("event_name_replacements"),
        )
        ws.title = new_tab
        all_changes[new_tab] = changes

        print(f"\n  [{new_tab}] {src} 기반, {len(changes)}개 셀 갱신")
        for coord, old, new in changes:
            print(f"    {coord}: '{old}' -> '{new}'")

        season_hits = warn_season_keywords(ws, new_tab)
        all_season_warnings[new_tab] = season_hits

    # 탭 순서 정렬 (오름차순): 역순으로 각 탭을 앞으로 이동
    for tab in reversed(sorted(UPDATES.keys())):
        if tab in wb.sheetnames:
            wb.move_sheet(tab, offset=-wb.sheetnames.index(tab))

    wb.save(OUTPUT_FILE)

    print(f"\n완료!")
    print(f"  생성 파일: {OUTPUT_FILE}")
    print(f"  탭 순서: {wb.sheetnames}")

    # 경고가 남은 탭 안내
    remaining = {t: hits for t, hits in all_season_warnings.items() if hits}
    if remaining:
        print(
            "\n  ※ 위 경고 셀의 이벤트 명칭을 갱신하려면:\n"
            "     1) Claude에게 '이벤트 명칭 자동 갱신' 요청\n"
            "     2) 또는 UPDATES['{탭명}']['event_name_replacements'] 에 직접 추가 후 재실행"
        )
    else:
        print("  [OK] 시즌·월 키워드 경고 없음")


def run_with_config(
    source_path: str,
    output_path: str,
    updates: dict,
    event_name_cfg: dict | None = None,
) -> dict:
    """Streamlit/외부 직접 호출용. 결과 dict + xlsx 바이트 반환."""
    import copy

    updates = copy.deepcopy(updates)

    if event_name_cfg:
        for tab_name, repls in event_name_cfg.get("event_name_replacements", {}).items():
            if tab_name in updates:
                updates[tab_name]["event_name_replacements"] = [tuple(r) for r in repls]

    wb = openpyxl.load_workbook(source_path)

    sheets_needed = {cfg["source_tab"] for cfg in updates.values()}
    for name in list(wb.sheetnames):
        if name not in sheets_needed:
            wb.remove(wb[name])

    all_changes: dict = {}
    all_season_warnings: dict = {}

    for new_tab, cfg in updates.items():
        src = cfg["source_tab"]
        if src not in wb.sheetnames:
            raise ValueError(f"소스 탭 '{src}' 없음. 사용 가능: {wb.sheetnames}")
        ws = wb[src]
        changes = apply_replacements(
            ws,
            cfg["replacements"],
            date_map=cfg.get("date_map"),
            event_name_replacements=cfg.get("event_name_replacements"),
        )
        ws.title = new_tab
        all_changes[new_tab] = changes
        all_season_warnings[new_tab] = warn_season_keywords(ws, new_tab)

    for tab in reversed(sorted(updates.keys())):
        if tab in wb.sheetnames:
            wb.move_sheet(tab, offset=-wb.sheetnames.index(tab))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)

    buf = io.BytesIO()
    wb.save(buf)

    result = {
        "output_path": output_path,
        "xlsx_bytes": buf.getvalue(),
        "tabs": list(wb.sheetnames),
        "changes": all_changes,
        "season_warnings": all_season_warnings,
    }

    # last_run_result.json 저장 (save_learning.py 용)
    try:
        run_log = {
            "output_path": output_path,
            "tabs": result["tabs"],
            "changes": {
                tab: [list(c) for c in chgs]
                for tab, chgs in all_changes.items()
            },
            "season_warnings": {
                tab: [list(w) for w in warns]
                for tab, warns in all_season_warnings.items()
            },
        }
        log_path = OUTPUT_JSON_DIR / "last_run_result.json"
        log_path.write_text(
            json.dumps(run_log, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass  # 로그 저장 실패는 메인 흐름에 영향 없음

    return result


if __name__ == "__main__":
    # Windows cp949 콘솔에서 utf-8 출력 강제
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    main()
