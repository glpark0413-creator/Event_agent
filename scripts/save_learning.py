#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
에이전트 학습 저장 스크립트

각 실행 결과를 output/agent_learning.json 에 누적 저장.
다음 실행 시 에이전트가 이 파일을 읽어 장르 키워드·보상 수량·이벤트 명칭 패턴을 재활용한다.

입력 (output/ 디렉터리 내):
  - event_names_config.json  : 장르·키워드·명칭 치환 규칙
  - last_run_result.json     : 실행 결과 (탭·변경 내역)
  - reward_scan_result.json  : 보상 수량 스캔 결과
  - reward_by_event.json     : 이벤트 섹션별 보상 패턴 (있으면 반영)

출력:
  - output/agent_learning.json : 누적 학습 데이터
"""
import io
import json
import sys
from datetime import date, datetime
from pathlib import Path

OUTPUT_DIR = Path("output")
OUTPUT_JSON_DIR = OUTPUT_DIR / "json"
LEGACY_LEARNING_FILE = OUTPUT_JSON_DIR / "agent_learning.json"  # 하위 호환용

# ─── 현재 프로젝트 설정 로드 ──────────────────────────────────────────────
_BASE_DIR = Path(__file__).resolve().parent.parent
_CURRENT_PROJECT_FILE = _BASE_DIR / "output" / "json" / "current_project.json"

def _resolve_learning_path(project_id: str) -> Path:
    """프로젝트별 학습 파일 경로 반환. 새 구조(output/projects/) 우선."""
    if project_id:
        # 새 구조 우선
        new_dir = _BASE_DIR / "output" / "projects" / project_id / "learning"
        new_dir.mkdir(parents=True, exist_ok=True)
        return new_dir / "agent_learning.json"
    return LEGACY_LEARNING_FILE


def load_json(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def extract_reward_qty_summary(reward_scan: dict) -> dict:
    """reward_scan_result.json summary_by_type → 보상명별 수량 요약."""
    summary: dict[str, dict] = {}
    for rtype, info in reward_scan.get("summary_by_type", {}).items():
        qty_range = info.get("quantity_range")
        for name in info.get("unique_names", []):
            summary[name] = {
                "type": rtype,
                "avg_quantity": qty_range["avg"] if qty_range else None,
                "min_quantity": qty_range["min"] if qty_range else None,
                "max_quantity": qty_range["max"] if qty_range else None,
                "unit": "",
                "has_quantity": qty_range is not None,
                "note": info.get("note", ""),
            }
    return summary


def update_accumulated(acc: dict, run: dict) -> dict:
    """누적 학습 데이터에 이번 실행 결과 병합."""

    # ── 장르 키워드 누적 ─────────────────────────────────────────────
    genre = run.get("genre", "")
    phrases = run.get("genre_phrases", [])
    if genre and phrases:
        existing = acc.setdefault("genre_keywords", {}).setdefault(genre, [])
        merged = list(dict.fromkeys(existing + phrases))  # 순서 유지 중복 제거
        acc["genre_keywords"][genre] = merged

    # ── 이벤트 명칭 패턴 누적 ────────────────────────────────────────
    for tab, repls in run.get("event_name_replacements", {}).items():
        bucket = acc.setdefault("event_name_patterns", {}).setdefault(tab, [])
        for pair in repls:
            if pair not in bucket:
                bucket.append(pair)

    # ── 보상 수량 패턴 누적 ──────────────────────────────────────────
    for name, info in run.get("reward_qty_summary", {}).items():
        bucket = acc.setdefault("reward_patterns", {})
        if name not in bucket:
            bucket[name] = {
                "type": info["type"],
                "has_quantity": info["has_quantity"],
                "quantity_samples": [],
                "note": info["note"],
                "occurrences": 0,
            }
        bucket[name]["occurrences"] += 1
        avg = info.get("avg_quantity")
        if avg is not None:
            bucket[name]["quantity_samples"].append(avg)

    # ── 확정 보상 치환 패턴 누적 (명칭 → 신규명) ─────────────────────
    for tab, repls in run.get("reward_replacements_applied", {}).items():
        bucket = acc.setdefault("reward_replacement_patterns", {}).setdefault(tab, [])
        for pair in repls:
            if pair not in bucket:
                bucket.append(pair)

    # ── 이벤트 유형별 보상 구성 패턴 누적 ────────────────────────────
    for etype, info in run.get("event_reward_patterns", {}).items():
        bucket = acc.setdefault("event_reward_patterns", {})
        if etype not in bucket:
            bucket[etype] = {
                "seen_count": 0,
                "top_reward_names": [],
                "quantity_stats": {},
            }

        bucket[etype]["seen_count"] = max(
            bucket[etype]["seen_count"],
            info.get("seen_count", 0),
        )

        # top_reward_names 병합 (중복 제거·순서 유지)
        existing_names = bucket[etype]["top_reward_names"]
        for name in info.get("top_reward_names", []):
            if name not in existing_names:
                existing_names.append(name)
        bucket[etype]["top_reward_names"] = existing_names[:10]  # 최대 10개

        # 수량 통계: 기존 샘플 수가 더 많으면 덮어쓰기
        for rtype, stats in info.get("quantity_stats", {}).items():
            existing_stat = bucket[etype]["quantity_stats"].get(rtype)
            if not existing_stat or stats.get("samples", 0) > existing_stat.get("samples", 0):
                bucket[etype]["quantity_stats"][rtype] = stats

    # ── 이벤트 유형 빈도 패턴 누적 ──────────────────────────────────────
    # analyze_event_patterns.py 결과에서 이벤트 유형별 등장률·우선순위 병합.
    # 샘플 수(total_tabs)가 더 많은 쪽의 데이터로 갱신한다.
    for etype, info in run.get("event_frequency_patterns", {}).items():
        bucket = acc.setdefault("event_frequency_patterns", {})
        existing = bucket.get(etype)
        incoming_total = info.get("total_tabs", 0)
        if not existing or incoming_total > existing.get("total_tabs", 0):
            bucket[etype] = {
                "count":          info.get("count", 0),
                "total_tabs":     incoming_total,
                "rate":           info.get("rate", 0.0),
                "rate_pct":       info.get("rate_pct", "0%"),
                "priority":       info.get("priority", "rare"),
                "title_examples": info.get("title_examples", []),
                "updated_at":     run.get("run_date", ""),
            }

    return acc


def main():
    # ── 프로젝트 경로 결정 ────────────────────────────────────────────────────
    import sys as _sys_sl
    _sys_sl.path.insert(0, str(Path(__file__).resolve().parent))
    from _project_config import load_project_paths as _lpp
    _proj_paths = _lpp()

    OUTPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_JSON_DIR.mkdir(exist_ok=True)

    if _proj_paths:
        _proj_paths.ensure_dirs()
        json_dir = _proj_paths.work_dir      # 세션 작업 파일 위치
    else:
        json_dir = OUTPUT_JSON_DIR

    cfg = load_json(json_dir / "event_names_config.json")
    last_run = load_json(json_dir / "last_run_result.json")
    reward_scan = load_json(json_dir / "reward_scan_result.json")
    reward_by_event = load_json(json_dir / "reward_by_event.json")
    event_pattern_analysis = load_json(json_dir / "event_pattern_analysis.json")

    reward_qty_summary = extract_reward_qty_summary(reward_scan)
    event_reward_patterns = reward_by_event.get("event_type_patterns", {})
    # analyze_event_patterns.py 결과에서 이벤트 유형 빈도 통계 추출
    event_frequency_patterns = event_pattern_analysis.get("event_type_frequency", {})

    # 보상 치환 규칙에서 "보상 명칭 치환" 항목 분리
    # event_name_replacements 중 팩·다이아·골드 등 보상 키워드 포함 항목을 보상 치환으로 분류
    REWARD_KEYS = ["팩", "다이아", "골드", "박스", "코인", "쿠폰", "뽑기"]
    reward_repls: dict[str, list] = {}
    event_repls: dict[str, list] = {}
    for tab, repls in cfg.get("event_name_replacements", {}).items():
        r_list, e_list = [], []
        for pair in repls:
            old_name = pair[0] if pair else ""
            if any(k in old_name for k in REWARD_KEYS):
                r_list.append(pair)
            else:
                e_list.append(pair)
        if r_list:
            reward_repls[tab] = r_list
        if e_list:
            event_repls[tab] = e_list

    run_entry = {
        "run_id": f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "run_date": date.today().isoformat(),
        "genre": cfg.get("genre", ""),
        "target_month": cfg.get("target_month", ""),
        "genre_phrases": cfg.get("genre_phrases", []),
        "tabs_created": last_run.get("tabs", []),
        "event_name_replacements": event_repls,
        "reward_replacements_applied": reward_repls,
        "reward_qty_summary": reward_qty_summary,
        "event_reward_patterns": event_reward_patterns,
        "event_frequency_patterns": event_frequency_patterns,
        "changes_count": {tab: len(chgs) for tab, chgs in last_run.get("changes", {}).items()},
    }

    # ── 저장 경로 결정 (프로젝트별 우선, 레거시 폴백) ─────────────────────────
    if _proj_paths:
        project_id = _proj_paths.project_id
        LEARNING_FILE = _proj_paths.agent_learning
        LEARNING_FILE.parent.mkdir(parents=True, exist_ok=True)
    else:
        project_id = ""
        if _CURRENT_PROJECT_FILE.exists():
            try:
                _cp = json.loads(_CURRENT_PROJECT_FILE.read_text(encoding="utf-8"))
                project_id = _cp.get("project_id", "")
            except Exception:
                pass
        LEARNING_FILE = _resolve_learning_path(project_id)

    # 누적 파일 로드
    if LEARNING_FILE.exists():
        with open(LEARNING_FILE, encoding="utf-8") as f:
            learning = json.load(f)
    else:
        learning = {
            "version": 1,
            "runs": [],
            "accumulated_learnings": {
                "genre_keywords": {},
                "event_name_patterns": {},
                "reward_patterns": {},
                "reward_replacement_patterns": {},
                "event_reward_patterns": {},
                "event_frequency_patterns": {},
            },
        }

    # 크롤링으로 생성된 파일에는 'runs' 키가 없을 수 있으므로 초기화
    if "runs" not in learning:
        learning["runs"] = []
    learning["runs"].append(run_entry)
    learning["last_updated"] = datetime.now().isoformat(timespec="seconds")
    learning["accumulated_learnings"] = update_accumulated(
        learning.get("accumulated_learnings", {}), run_entry
    )

    with open(LEARNING_FILE, "w", encoding="utf-8") as f:
        json.dump(learning, f, ensure_ascii=False, indent=2)

    # ── 레거시 파일에도 동일 내용 동기화 (하위 호환) ────────────────────────
    if project_id and LEARNING_FILE != LEGACY_LEARNING_FILE:
        with open(LEGACY_LEARNING_FILE, "w", encoding="utf-8") as f:
            json.dump(learning, f, ensure_ascii=False, indent=2)

    total_runs = len(learning["runs"])
    acc = learning["accumulated_learnings"]
    genre_count = sum(len(v) for v in acc.get("genre_keywords", {}).values())
    reward_count = len(acc.get("reward_patterns", {}))
    event_reward_count = len(acc.get("event_reward_patterns", {}))
    event_freq_count = len(acc.get("event_frequency_patterns", {}))

    if _proj_paths:
        dest_display = str(LEARNING_FILE)
    else:
        dest_str = f"projects/{project_id}/" if project_id else ""
        dest_display = f"output/json/{dest_str}agent_learning.json"
    print(f"학습 저장 완료: {dest_display}")
    if project_id:
        print(f"  프로젝트: {project_id}")
    print(f"  누적 실행: {total_runs}회")
    print(f"  장르 키워드 누적:        {genre_count}개")
    print(f"  보상 패턴 누적:          {reward_count}종")
    print(f"  이벤트 유형 보상 패턴:   {event_reward_count}종")
    print(f"  이벤트 유형 빈도 패턴:   {event_freq_count}종")


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    main()
