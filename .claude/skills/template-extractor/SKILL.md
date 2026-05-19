# template-extractor 스킬

## 역할
`raw_sheet_data.json` + LLM이 생성한 `template.json` 을 기반으로 통계 정보를 추출해 `history_stats.json` 을 생성한다.

## 트리거 조건
Phase 1에서 LLM이 `template.json` 을 저장한 직후

## 실행 방법
```bash
python .claude/skills/template-extractor/scripts/extract_template.py
```

## 전제 조건
- `output/raw_sheet_data.json` 존재 (sheets-reader 스킬 완료 후)
- `output/template.json` 존재 (LLM이 열 구조 해석 후 저장)

## 출력 파일: `output/history_stats.json`

```json
{
  "monthly_avg": 6,
  "monthly_counts": {
    "2025-01": 5,
    "2025-02": 6,
    "2025-03": 7
  },
  "category_ratio": {
    "출석": 0.30,
    "미션": 0.50,
    "한정": 0.20
  },
  "reward_range": {
    "min": 50,
    "max": 500,
    "avg": 180,
    "sample": ["다이아몬드 50개", "다이아몬드 100개", "골드 500개"]
  },
  "meta": {
    "total_data_rows": 42,
    "date_col_index": 2,
    "category_col_index": 1,
    "reward_col_index": 4
  }
}
```

## 열 자동 감지 기준
| 열 종류 | 감지 기준 |
|---|---|
| 날짜 열 | `template.json` 에서 `type: "date"` 또는 이름에 "시작"/"날짜" 포함 |
| 카테고리 열 | 이름에 "카테고리" 포함 또는 `type: "enum"` |
| 보상 열 | 이름에 "보상" 포함 |

## 특이사항
- 날짜 파싱 실패 행이 있으면 WARNING 출력 (스크립트는 계속 진행)
- 데이터가 없으면 기본값(`monthly_avg: 6`)으로 저장
- 보상 수치는 텍스트에서 숫자를 추출해 min/max/avg 계산
