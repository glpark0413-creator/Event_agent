# event-generator 스킬

## 역할
Phase 2에서 시즌·장르 맥락을 반영한 이벤트 초안을 생성한다. 스크립트 없이 LLM이 직접 처리한다.

## 트리거 조건
Phase 1 완료 (요청자 확인 포함) 후 Phase 2 진입 시

## 참조 파일
- `output/template.json` — 열 구조 및 보상 범위
- `output/history_stats.json` — 월별 평균, 카테고리 비율
- `.claude/skills/event-generator/references/season_calendar.md` — 시즌 캘린더

## 생성 절차

### 1. 이벤트 수 결정
```
이벤트 수 = history_stats.monthly_avg ± 1 (요청자 명시 지시 없을 시)
```

### 2. 카테고리 배분
`category_ratio` 비율에 맞게 이벤트 수 분배.  
예) monthly_avg=6, 출석30%/미션50%/한정20% → 출석 2개, 미션 3개, 한정 1개

### 3. 시즌 맥락 파악
- `season_calendar.md` 에서 대상 연월에 해당하는 이벤트 확인
- LLM 지식으로 보완 (KBO/NPB 시즌, 공휴일 등)

### 4. 문구 생성 공식
```
이벤트명 = 시즌 키워드 + 야구 용어 + 이벤트 유형
예:
  골든위크(시즌) + 홈런더비(야구) + 챌린지(유형) → "골든위크 홈런더비 챌린지"
  추석(시즌) + 9회말 역전(야구) + 미션(유형) → "추석 역전 미션"
```
- 항상 한국어로 생성 (번역은 이 에이전트 범위 밖)
- 타겟 마켓의 시즌 맥락을 반영하되 문구 자체는 한국어

### 5. 보상 수치 결정
- `reward_range.min` ~ `reward_range.max` 범위 내
- 카테고리별 차등 적용 (한정 > 미션 > 출석 순으로 보상 높게)
- 범위 데이터가 없으면 `reward_range.sample` 의 패턴을 참조

## 자기검증 체크리스트
생성 후 다음을 순서대로 확인한다:
- [ ] 이벤트 수가 monthly_avg ± 1 범위 내인가?
- [ ] 모든 이벤트가 required: true 열을 전부 채웠는가?
- [ ] 임시 일정이 대상 연월 범위 내인가?
- [ ] 보상 수치가 reward_range 범위를 벗어나지 않는가?
- [ ] 이벤트명 또는 상세내용에 야구 용어/시즌 맥락이 포함되어 있는가?

실패 항목이 있으면 해당 이벤트만 수정 후 재검증. 최대 2회.

## 출력 파일: `output/draft_events.json`
CLAUDE.md 의 Phase 2 섹션에 정의된 스키마로 저장.
