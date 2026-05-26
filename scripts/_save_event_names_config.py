#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""event_names_config.json 저장 스크립트 (임시)"""
import json
from pathlib import Path

data = {
  "genre": "야구",
  "target_month": "2026-06",
  "genre_phrases": ["전반기","올스타","홈런","만루","삼진","역전","클린업","완투","더블헤더","승부","불꽃","여름","뜨거운","전력질주","황금장갑"],
  "event_name_replacements": {
    "260611": [
      ["1. 얼리썸머 14일 출석 이벤트!", "1. 전반기 14일 출석 이벤트!"],
      ["2. 초여름의 그라운드 응모권 이벤트!", "2. 한여름의 그라운드 응모권 이벤트!"],
      ["3. 쿨 서머 워밍업 플레이 미션 이벤트!", "3. 홈런더비 열전 플레이 미션 이벤트!"],
      ["4. 불펜의 온도를 높여라! 교환소 이벤트", "4. 만루 찬스! 교환소 이벤트"],
      ["5. 5월의 끝자락 야구공 찾기 이벤트!", "5. 6월의 뜨거운 야구공 찾기 이벤트!"],
      ["8. 승부 예측 이벤트!", "8. 올스타전 승부 예측 이벤트!"],
      ["초여름의 그라운드 응모권 이벤트", "한여름의 그라운드 응모권 이벤트"],
      ["쿨 서머 워밍업 플레이 미션 이벤트", "홈런더비 열전 플레이 미션 이벤트"]
    ],
    "260618": [
      ["1. 포인트 레이스 이벤트", "1. 여름 포인트 레이스 이벤트"],
      ["2. 룰렛 이벤트", "2. 황금장갑 룰렛 이벤트"],
      ["3. 빙고 이벤트", "3. 전력질주 빙고 이벤트"]
    ]
  }
}

p = Path("output/json/event_names_config.json")
p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"저장 완료: {p}")

# 검증
loaded = json.loads(p.read_text(encoding="utf-8"))
first = loaded["event_name_replacements"]["260611"][0]
print(f"검증 - 첫번째 교체: {first[0]} → {first[1]}")
