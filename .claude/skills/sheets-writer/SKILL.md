# sheets-writer 스킬

## 역할
`confirmed_events.json` 을 신규 Google Sheets에 기록한다. 기존 Sheets의 서식(헤더 색상, 열 너비, 행 고정)을 복제한다.

## 트리거 조건
Phase 3 전체 확정 후 Phase 4 진입 시

## 실행 방법
```bash
python .claude/skills/sheets-writer/scripts/write_sheet.py
```

## 입력 파일
| 파일 | 용도 |
|---|---|
| `output/confirmed_events.json` | 확정된 이벤트 목록 |
| `output/template.json` | 열 순서 및 원본 열 이름 |
| `output/raw_sheet_data.json` | 서식 정보 (format_info) |

## 출력
- 신규 Google Sheets URL (stdout 에 출력)
- `output/run_log.json` 갱신

## 시트 명명 규칙
```
이벤트기획_{대상연월}_{타임스탬프}
예: 이벤트기획_2025-05_20250501_1030
```
재실행 시마다 새 이름으로 생성 (이전 시트는 Drive에 유지됨)

## 서식 복제 항목
| 항목 | 구현 방법 |
|---|---|
| 헤더 배경색 | `repeatCell` batchUpdate |
| 헤더 텍스트 볼드 | `repeatCell` batchUpdate |
| 첫 행 고정 | `updateSheetProperties` (frozenRowCount) |
| 열 너비 | `updateDimensionProperties` |

## 에러 처리
- API 오류 → 최대 3회 자동 재시도
- 3회 모두 실패 → 에스컬레이션 메시지 출력 후 종료 (run_log.json 에 기록)

## 인증
read_sheet.py 와 동일한 인증 방식 사용 (token.json / service_account.json)
