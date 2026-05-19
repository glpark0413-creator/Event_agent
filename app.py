#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
이벤트 탭 생성기 — Streamlit 웹 앱 (역할 분리 방식)

역할:
  - Claude.ai (구독) : 이벤트 명칭 제안 → event_names_config.json 생성
  - 이 앱             : xlsx 탭 생성 + 다운로드 (Anthropic API 불필요)
"""
import copy
import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))
from scripts.create_tabs import UPDATES, run_with_config

# ── 기본값 ───────────────────────────────────────────────────────────────────
DEFAULT_SOURCE = (
    r"C:\Users\glpark0413_pc\Desktop\업무 자동화\Event_Agent"
    r"\Readdocs\[FB_GL] 2026 라이브 이벤트.xlsx"
)
OUTPUT_DIR = Path("output")

# ── 페이지 설정 ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="이벤트 탭 생성기", page_icon="⚾", layout="wide")
st.title("⚾ 이벤트 탭 생성기")
st.caption(
    "Claude.ai에서 이벤트 명칭을 제안받아 xlsx를 자동 생성합니다. "
    "Anthropic API 키 불필요."
)


# ── ① 소스 파일 ──────────────────────────────────────────────────────────────
st.header("① 소스 파일")

source_path = st.text_input("소스 xlsx 경로", value=DEFAULT_SOURCE)
output_filename = st.text_input(
    "출력 파일명",
    value="이벤트기획_신규탭.xlsx",
    help="output/ 폴더 안에 저장됩니다.",
)

if st.button("📂 파일 확인"):
    if Path(source_path).exists():
        st.success(f"파일 확인 OK: {Path(source_path).name}")
    else:
        st.error(f"파일을 찾을 수 없습니다:\n{source_path}")


# ── ② 탭 설정 (고급) ─────────────────────────────────────────────────────────
with st.expander("② 탭 설정 보기/편집 (고급)", expanded=False):
    st.caption(
        "기본값: **260611** (← 260528), **260618** (← 260604) 탭을 생성합니다.  \n"
        "다른 탭을 생성하려면 아래 JSON을 직접 수정하세요."
    )

    # UPDATES의 tuple → list 변환 (JSON 직렬화)
    updates_for_display = {
        k: {
            **v,
            "replacements": [list(r) for r in v["replacements"]],
            "event_name_replacements": [
                list(r) for r in v.get("event_name_replacements", [])
            ],
        }
        for k, v in UPDATES.items()
    }

    updates_json_str = st.text_area(
        "UPDATES 설정 (JSON)",
        value=json.dumps(updates_for_display, ensure_ascii=False, indent=2),
        height=420,
        key="updates_json",
    )

    try:
        custom_updates = json.loads(updates_json_str)
        st.success("JSON 형식 OK")
    except json.JSONDecodeError as e:
        st.error(f"JSON 파싱 오류: {e}")
        custom_updates = updates_for_display


# ── ③ 이벤트 명칭 설정 ───────────────────────────────────────────────────────
st.header("③ 이벤트 명칭 설정 (선택)")

st.info(
    "**Claude.ai 에서 이벤트명을 제안받아 아래에 붙여넣으세요.**\n\n"
    "Claude.ai 에 이렇게 요청하세요:\n"
    "> \"260611, 260618 탭의 이벤트 명칭을 야구/6월 테마로 제안해줘. "
    "event_names_config.json 형식으로 출력해줘.\"\n\n"
    "비워두면 날짜·이달의 선수팩 패턴 치환만 적용됩니다."
)

event_config_str = st.text_area(
    "event_names_config.json 내용",
    height=220,
    placeholder=(
        "{\n"
        '  "event_name_replacements": {\n'
        '    "260611": [\n'
        '      ["구 이벤트명", "새 이벤트명"]\n'
        "    ],\n"
        '    "260618": []\n'
        "  }\n"
        "}"
    ),
    key="event_config",
)

event_name_cfg = None
if event_config_str.strip():
    try:
        event_name_cfg = json.loads(event_config_str)
        total = sum(
            len(v)
            for v in event_name_cfg.get("event_name_replacements", {}).values()
        )
        st.success(f"이벤트 명칭 설정 로드 완료: {total}개 치환 규칙")
    except json.JSONDecodeError as e:
        st.error(f"JSON 파싱 오류: {e}")
        event_name_cfg = None


# ── ④ xlsx 생성 ──────────────────────────────────────────────────────────────
st.header("④ xlsx 생성")

if st.button("🚀 xlsx 생성하기", type="primary", use_container_width=True):
    if not Path(source_path).exists():
        st.error(f"소스 파일을 찾을 수 없습니다:\n{source_path}")
        st.stop()

    output_path = str(OUTPUT_DIR / output_filename)

    with st.spinner("xlsx 생성 중... (수 초 소요)"):
        try:
            result = run_with_config(
                source_path,
                output_path,
                copy.deepcopy(custom_updates),
                event_name_cfg,
            )
        except Exception as e:
            st.error(f"생성 중 오류 발생:\n{e}")
            st.stop()

    st.success(f"✅ 생성 완료! — `{output_filename}`")

    # 변경 내역
    for tab, changes in result["changes"].items():
        with st.expander(f"**{tab}** — {len(changes)}개 셀 갱신", expanded=True):
            for coord, old, new in changes[:40]:
                st.text(f"  {coord}: '{old}' → '{new}'")
            if len(changes) > 40:
                st.caption(f"  ... 외 {len(changes) - 40}개")

    # 시즌 키워드 경고
    for tab, warnings in result["season_warnings"].items():
        if warnings:
            lines = "\n".join(
                f"  {coord}: {val[:70]}" for coord, val in warnings[:5]
            )
            extra = f"\n  ... 외 {len(warnings)-5}개" if len(warnings) > 5 else ""
            st.warning(
                f"⚠ [{tab}] 시즌·월 키워드가 남은 셀 {len(warnings)}개 "
                f"— 이벤트 명칭 확인 권장\n{lines}{extra}"
            )

    # 다운로드
    st.download_button(
        label="📥 xlsx 다운로드",
        data=result["xlsx_bytes"],
        file_name=output_filename,
        mime=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        use_container_width=True,
    )
