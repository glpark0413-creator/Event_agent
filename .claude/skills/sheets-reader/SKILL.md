# sheets-reader 스킬

## 역할
xlsx 파일(또는 Google Sheets URL)에서 전체 데이터와 서식 정보를 읽어 `output/raw_sheet_data.json` 으로 저장한다.

## 트리거 조건
Phase 1 시작 시 (요청자로부터 xlsx 파일 경로를 받은 직후)

## 실행 방법
```bash
# xlsx 파일 (기본 방식)
python .claude/skills/sheets-reader/scripts/read_sheet.py --file "<xlsx 파일 경로>"

# Google Sheets URL (API 인증 필요 시)
python .claude/skills/sheets-reader/scripts/read_sheet.py --url "<Sheets URL>"
```

## 출력 파일: `output/raw_sheet_data.json`

```json
{
  "spreadsheet_id": "events",
  "spreadsheet_url": null,
  "source_file": "C:/Downloads/events.xlsx",
  "sheet_name": "이벤트현황",
  "sheet_id": 0,
  "headers": ["이벤트명", "카테고리", "시작일", "종료일", "보상"],
  "rows": [
    ["골든위크 챌린지", "미션", "2025/04/29", "2025/05/05", "다이아몬드 50개"],
    ...
  ],
  "total_rows": 42,
  "format_info": {
    "column_widths": [200, 100, 120, 120, 150],
    "frozen_rows": 1,
    "header_background_color": {"red": 0.26, "green": 0.52, "blue": 0.96},
    "header_text_bold": true,
    "header_text_color": {"red": 1.0, "green": 1.0, "blue": 1.0}
  }
}
```

## 에러 처리
- 파일 경로 오류 → `FileNotFoundError` 출력 후 종료
- openpyxl 미설치 → 설치 안내 후 종료
- URL 모드 시 권한 오류 → Google API 오류 메시지 출력 후 종료

## 의존 패키지
- `openpyxl>=3.1.0` (xlsx 읽기)
- `google-api-python-client` 등 (--url 모드 전용)
