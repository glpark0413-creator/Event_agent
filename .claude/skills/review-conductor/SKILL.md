# review-conductor 스킬

## 역할
Phase 3 인터랙티브 검토를 진행한다. 이벤트를 순차 제시하고, 요청자 응답을 반영해 `confirmed_events.json` 을 갱신한다.

## 트리거 조건
Phase 2 완료 후 Phase 3 진입 시, 그리고 요청자 응답이 있을 때마다

## 제시 형식
```
─────────────────────────────
[{N}/{전체}] {이벤트명}
  기간: {시작일} ~ {종료일}
  카테고리: {카테고리}
  보상: {보상 내용}
  상세: {상세 내용}

→ 유지 / 수정할 항목과 내용을 입력해주세요.
─────────────────────────────
```

## 응답 처리 방법

| 요청자 입력 | 처리 방법 | 스크립트 명령어 |
|---|---|---|
| "유지" | confirmed 처리 후 다음 이벤트 | `python ... update_draft.py --event-id {id} --confirm` |
| "기간 5/6까지" | 종료일 수정 후 재제시 | `python ... update_draft.py --event-id {id} --field 종료일 --value "2025/05/06"` |
| "보상을 100개로" | 보상 수정 후 재제시 | `python ... update_draft.py --event-id {id} --field 보상 --value "다이아몬드 100개"` |
| "이름을 X로 바꿔줘" | 이벤트명 수정 후 재제시 | `python ... update_draft.py --event-id {id} --field 이벤트명 --value "X"` |
| "추가해줘" | 새 이벤트 생성 + 큐 끝에 추가 | `python ... update_draft.py --add '{...}'` |
| "삭제해줘" / "빼줘" | 이벤트 삭제 후 다음으로 | `python ... update_draft.py --delete-id {id}` |
| "다시 검토" (최종 단계에서) | 전체 초기화 | `python ... update_draft.py --reset-all` |
| 응답 모호 | 재질문 (스크립트 미호출) | — |

## 스크립트 경로
```bash
python .claude/skills/review-conductor/scripts/update_draft.py [옵션]
```

## 세션 재개
`output/confirmed_events.json` 의 `review_progress.confirmed` 를 확인해 그 다음 인덱스부터 시작.
이미 `status: confirmed` 인 이벤트는 건너뜀.

## 종료 조건
모든 이벤트 `status: confirmed` 후 최종 확정 질문:
```
전체 {N}개 이벤트가 확정되었습니다.
최종 확정하고 Google Sheets를 생성할까요? (전체 확정 / 다시 검토)
```
