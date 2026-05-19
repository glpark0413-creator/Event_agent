# 모바일 스포츠 게임 이벤트 기획 자동화 에이전트 — 통합 설계서

> **용도**: Claude Code 구현 참조용 계획서
> **작성 기준**: 기존 Google Sheets 참조 → 신규 이벤트 기획안 생성 → 일정/내용 인터랙티브 검토 → Google Sheets 출력

---

## 1. 작업 컨텍스트 문서

### 1-1. 배경 및 목적

모바일 스포츠(야구) 게임의 이벤트 기획 담당자가 매월 반복적으로 수행하는 이벤트 기획안 작성 작업을 자동화한다. 기존 Google Sheets의 양식·포맷을 100% 보존하면서, 시즌·마켓 트렌드 및 장르 특화 문구를 반영한 신규 이벤트 기획안을 빠르게 생성하고, 담당자의 검토를 거쳐 최종 Google Sheets로 출력하는 것이 목적이다.

### 1-2. 범위

| 포함 | 제외 |
|------|------|
| 기존 Sheets 구조 분석 및 템플릿 추출 | 이벤트 실제 개발/구현 |
| 시즌·장르 기반 이벤트 문구/제목 생성 | 게임 내 데이터 연동 |
| 이벤트 수 자동 판단 (월별 평균 기반) | 다국어 번역 |
| 인터랙티브 일정·내용 검토 (Phase 3) | 이미지·배너 생성 |
| Google Sheets API 출력 | 타 메신저/시스템 연동 |

### 1-3. 입출력 정의

**입력**
- 기존 이벤트 Google Sheets URL (읽기 권한)
- 대상 연월 (예: `2025-05`)
- 타겟 마켓 (예: 일본, 한국, 글로벌)
- 주력 장르 키워드 (기본값: 야구)

**출력**
- 신규 이벤트 기획안이 담긴 Google Sheets URL (쓰기 권한 계정으로 생성)
- 중간 산출물: `/output/` 내 JSON 파일들 (단계별 보존)

### 1-4. 제약조건

- 기존 Sheets의 열(Column) 구조, 데이터 포맷, 카테고리 분류를 변경하지 않는다
- Google Sheets API 사용 (OAuth 2.0 인증 또는 서비스 계정)
- Phase 3 인터랙션은 Claude Code 터미널 대화 방식으로 진행
- 이벤트 수는 기존 문서의 월별 평균에서 ±1 범위 내로 생성 (명시적 지시 없을 시)

### 1-5. 용어 정의

| 용어 | 정의 |
|------|------|
| 기존 문서 | 담당자가 URL로 제공하는 참조용 Google Sheets |
| 양식 템플릿 | 기존 문서에서 추출한 열 구조 + 포맷 정의 |
| 이벤트 초안 | Phase 2에서 생성된 미확정 기획안 (임시 일정 포함) |
| 확정 기획안 | Phase 3 검토 완료 후 최종 승인된 이벤트 데이터 |
| 타겟 시즌 | 대상 연월에 해당하는 시즌 이벤트 맥락 (골든위크, 추석 등) |

---

## 2. 워크플로우 정의

### 2-1. 전체 흐름도

```
[시작: 요청자 입력]
    │  - 기존 Sheets URL
    │  - 대상 연월, 타겟 마켓, 장르
    ▼
[Phase 1] 기존 문서 분석
    │  스크립트: Sheets API로 데이터 읽기
    │  LLM: 열 구조·포맷·카테고리 의미 해석
    │  산출물: template.json, history_stats.json
    ▼
[Phase 2] 이벤트 초안 생성
    │  LLM: 시즌 맥락 판단 + 이벤트 수 결정 + 문구 생성
    │  산출물: draft_events.json
    ▼
[Phase 3] 인터랙티브 검토
    │  LLM: 이벤트별 순차 제시
    │  요청자: 일정·내용·보상 수정 또는 유지 입력
    │  산출물: confirmed_events.json
    ▼
[Phase 4] Google Sheets 출력
    │  스크립트: Sheets API로 신규 시트 생성 + 데이터 기록
    │  산출물: 최종 Sheets URL
    ▼
[완료: URL 반환]
```

### 2-2. 단계별 상세 정의

---

#### Phase 1 — 기존 문서 분석

| 항목 | 내용 |
|------|------|
| **처리 주체** | 스크립트(Sheets API 읽기) + LLM(구조 해석) |
| **입력** | 기존 Sheets URL |
| **출력** | `template.json` (열 구조·포맷), `history_stats.json` (월별 이벤트 수 통계) |
| **성공 기준** | 필수 열(이벤트명, 기간, 보상, 상세내용 최소 포함) 추출 완료 + 월별 평균 이벤트 수 계산 완료 |
| **검증 방법** | 스키마 검증 — 필수 필드 존재 여부 체크 |
| **실패 시 처리** | Sheets 접근 오류 → 에스컬레이션(요청자에게 권한 확인 요청) / 열 구조 파악 불충분 → 자동 재시도 1회 후 에스컬레이션 |

**LLM 판단 영역**
- 열 이름이 약어·비표준 명칭일 때 의미 추론 (예: `ev_nm` → 이벤트명)
- 날짜 포맷 다양성 해석 (예: `4/29~5/5`, `2025.04.29-2025.05.05`)
- 카테고리 분류 체계 파악 (출석, 미션, 한정, 상시 등)

---

#### Phase 2 — 이벤트 초안 생성

| 항목 | 내용 |
|------|------|
| **처리 주체** | LLM |
| **입력** | `template.json`, `history_stats.json`, 대상 연월, 타겟 마켓, 장르 |
| **출력** | `draft_events.json` (임시 일정 포함 이벤트 목록) |
| **성공 기준** | ① 이벤트 수가 월별 평균 ±1 범위 내 / ② 모든 이벤트가 기존 필수 열을 채움 / ③ 임시 일정이 대상 연월 범위 내 |
| **검증 방법** | 규칙 기반(이벤트 수·날짜 범위) + LLM 자기 검증(문구 품질·장르 적합성) |
| **실패 시 처리** | 규칙 위반 → 자동 재시도 최대 2회 / 품질 기준 미달 → 재생성 후 재검증 |

**LLM 판단 영역**
- 대상 연월에 해당하는 시즌 이벤트 맥락 파악 (공휴일, 스포츠 시즌 일정 등)
- 카테고리별 이벤트 배분 (출석/미션/한정 비율을 기존 패턴에서 추론)
- 장르 특화 문구 생성 (야구 용어·상황 활용)
- 이벤트 수 결정 (기존 월별 평균 참조)

**이벤트 문구 생성 기준**
```
시즌 맥락 + 장르 특화 + 타겟 마켓
예시 조합:
  - 골든위크(시즌) + 홈런더비(야구) + 일본(마켓) → "골든위크 홈런더비 챌린지"
  - 여름방학(시즌) + 9회말 역전(야구) + 글로벌 → "Summer Comeback 역전 미션"
```

---

#### Phase 3 — 인터랙티브 검토

| 항목 | 내용 |
|------|------|
| **처리 주체** | LLM(진행·반영) + 요청자(판단) |
| **입력** | `draft_events.json` |
| **출력** | `confirmed_events.json` |
| **성공 기준** | 모든 이벤트에 대해 요청자의 명시적 승인("유지" 또는 수정 완료) 확인 |
| **검증 방법** | 규칙 기반 — 전체 이벤트 수만큼 확인 루프 완료 여부 |
| **실패 시 처리** | 요청자 응답 모호 → 에이전트가 재질문 / 세션 중단 → `confirmed_events.json`에 진행 상태 저장 후 재개 가능 |

**인터랙션 프로토콜**
```
에이전트 제시 형식:
─────────────────────────────
[N/전체] {이벤트명}
  기간: {임시 시작일} ~ {임시 종료일}
  카테고리: {카테고리}
  보상: {보상 내용}
  상세: {상세 내용}

→ 유지 / 수정할 항목과 내용을 입력해주세요.
─────────────────────────────

수정 입력 예시:
  "기간 5/6까지로 변경"
  "보상을 다이아 100개로 수정"
  "제목을 '봄맞이 홈런 챌린지'로 바꿔줘"
  "유지"
```

**분기 조건**
- 요청자가 이벤트 추가 요청 시 → 새 항목 생성 후 검토 큐에 추가
- 요청자가 이벤트 삭제 요청 시 → 해당 항목 제거 후 다음으로 진행
- 전체 검토 완료 후 요청자 최종 확인("전체 확정") 받으면 Phase 4 진입

---

#### Phase 4 — Google Sheets 출력

| 항목 | 내용 |
|------|------|
| **처리 주체** | 스크립트(Sheets API) |
| **입력** | `confirmed_events.json`, `template.json` |
| **출력** | 신규 Google Sheets URL |
| **성공 기준** | ① 신규 시트 생성 완료 / ② 모든 이벤트 행 기록 완료 / ③ 기존 양식(열 순서·포맷) 일치 |
| **검증 방법** | 스키마 검증 — 출력 시트 열 구조와 `template.json` 일치 여부 비교 |
| **실패 시 처리** | API 오류 → 자동 재시도 최대 3회 / 권한 오류 → 에스컬레이션 |

---

### 2-3. 상태 전이 요약

```
IDLE
  → [요청자 입력 수신] → ANALYZING
ANALYZING
  → [분석 성공] → DRAFTING
  → [분석 실패·에스컬레이션] → WAITING_USER
DRAFTING
  → [초안 생성 성공] → REVIEWING
  → [재시도 초과] → WAITING_USER
REVIEWING
  → [이벤트별 순차 확인 중] → REVIEWING (루프)
  → [전체 확정] → OUTPUTTING
  → [세션 중단] → PAUSED (재개 가능)
OUTPUTTING
  → [Sheets 생성 성공] → DONE
  → [API 실패·에스컬레이션] → WAITING_USER
DONE
```

---

## 3. 구현 스펙

### 3-1. 폴더 구조

```
/event-planner-agent
  ├── CLAUDE.md                          # 메인 에이전트 지침 (오케스트레이터)
  ├── /.claude
  │   ├── /skills
  │   │   ├── /sheets-reader             # Google Sheets 읽기
  │   │   │   ├── SKILL.md
  │   │   │   └── /scripts
  │   │   │       └── read_sheet.py
  │   │   ├── /template-extractor        # 양식 템플릿 추출·저장
  │   │   │   ├── SKILL.md
  │   │   │   └── /scripts
  │   │   │       └── extract_template.py
  │   │   ├── /event-generator           # 이벤트 문구·초안 생성
  │   │   │   ├── SKILL.md
  │   │   │   └── /references
  │   │   │       └── season_calendar.md # 시즌·공휴일 참조 데이터
  │   │   ├── /review-conductor          # Phase 3 인터랙션 진행
  │   │   │   ├── SKILL.md
  │   │   │   └── /scripts
  │   │   │       └── update_draft.py
  │   │   └── /sheets-writer             # Google Sheets 출력
  │   │       ├── SKILL.md
  │   │       └── /scripts
  │   │           └── write_sheet.py
  │   └── /agents
  │       └── (단일 에이전트 구조 — 서브에이전트 없음)
  ├── /output
  │   ├── template.json                  # Phase 1 산출물
  │   ├── history_stats.json             # Phase 1 산출물
  │   ├── draft_events.json              # Phase 2 산출물
  │   ├── confirmed_events.json          # Phase 3 산출물
  │   └── run_log.json                   # 전체 실행 로그
  └── /docs
      └── google_auth_setup.md           # Google API 인증 설정 가이드
```

### 3-2. 에이전트 구조

**단일 에이전트 채택 근거**
- 4개 Phase가 순차적 의존 관계(앞 단계 산출물 → 다음 단계 입력)
- 각 Phase 간 컨텍스트 공유가 빈번 (템플릿 정보가 전 단계에 걸쳐 참조됨)
- 워크플로우 분기가 단순하고 Phase 3 인터랙션 상태를 하나의 에이전트가 관리하는 것이 자연스러움

→ CLAUDE.md 단일 파일이 전체 오케스트레이션 담당

### 3-3. CLAUDE.md 핵심 섹션 목록

1. **역할 정의** — 이벤트 기획 자동화 에이전트 목적 및 행동 원칙
2. **입력 수집 절차** — 시작 시 요청자에게 받아야 할 4가지 정보
3. **Phase별 실행 지침** — 각 Phase 진입 조건, 호출할 스킬, 산출물 저장 경로
4. **양식 보존 원칙** — 기존 열 구조 변경 금지 규칙
5. **이벤트 수 결정 규칙** — 월별 평균 ±1 계산 방법
6. **Phase 3 인터랙션 프로토콜** — 제시 형식, 수정 반영 방법, 종료 조건
7. **에스컬레이션 기준** — 언제 요청자에게 확인을 요청하는가
8. **실패·재시도 정책** — Phase별 최대 재시도 횟수

### 3-4. 스킬 목록 및 트리거 조건

| 스킬명 | 역할 | 트리거 조건 |
|--------|------|------------|
| `sheets-reader` | Google Sheets URL에서 전체 데이터 읽기 | Phase 1 시작 시 |
| `template-extractor` | 읽은 데이터에서 열 구조·포맷·통계 추출 | Phase 1, sheets-reader 완료 후 |
| `event-generator` | 시즌·장르 기반 이벤트 문구 및 초안 생성 | Phase 2 시작 시 |
| `review-conductor` | Phase 3 인터랙션 진행 및 수정 사항 반영 | Phase 3 시작 시, 요청자 응답마다 |
| `sheets-writer` | 확정 데이터를 신규 Google Sheets에 기록 | Phase 4 시작 시 (전체 확정 후) |

### 3-5. 주요 산출물 파일 형식

**`template.json`** — 열 구조 및 포맷 정의
```json
{
  "columns": [
    { "index": 0, "name": "이벤트명", "type": "string", "required": true },
    { "index": 1, "name": "카테고리", "type": "enum", "values": ["출석", "미션", "한정"], "required": true },
    { "index": 2, "name": "시작일", "type": "date", "format": "YYYY/MM/DD", "required": true },
    { "index": 3, "name": "종료일", "type": "date", "format": "YYYY/MM/DD", "required": true },
    { "index": 4, "name": "보상", "type": "string", "required": true },
    { "index": 5, "name": "상세내용", "type": "string", "required": false }
  ]
}
```

**`history_stats.json`** — 월별 이벤트 수 통계
```json
{
  "monthly_avg": 6,
  "monthly_counts": { "2025-01": 5, "2025-02": 6, "2025-03": 7 },
  "category_ratio": { "출석": 0.3, "미션": 0.5, "한정": 0.2 }
}
```

**`draft_events.json` / `confirmed_events.json`** — 이벤트 목록
```json
{
  "target_month": "2025-05",
  "events": [
    {
      "id": 1,
      "status": "pending",
      "이벤트명": "골든위크 홈런더비 챌린지",
      "카테고리": "미션",
      "시작일": "2025/04/29",
      "종료일": "2025/05/05",
      "보상": "다이아몬드 50개",
      "상세내용": "기간 내 홈런 10개 달성 시 보상 지급"
    }
  ],
  "review_progress": { "confirmed": 0, "total": 6 }
}
```

**`run_log.json`** — 실행 로그 (에스컬레이션·실패 이력 포함)
```json
{
  "run_id": "2025-05-01T10:00:00",
  "phases": [
    { "phase": 1, "status": "success", "timestamp": "..." },
    { "phase": 2, "status": "retried", "attempts": 2, "timestamp": "..." }
  ],
  "escalations": []
}
```

### 3-6. Google API 연동 요건

- **인증 방식**: OAuth 2.0 (개인 계정) 또는 서비스 계정 JSON 키
- **필요 스코프**: `https://www.googleapis.com/auth/spreadsheets`
- **사용 API**: Google Sheets API v4
  - `spreadsheets.values.get` — Phase 1 읽기
  - `spreadsheets.create` + `spreadsheets.values.update` — Phase 4 쓰기
- **인증 설정 참조**: `/docs/google_auth_setup.md`

---

## 4. 설계 결정 사항 및 근거

| 결정 | 선택 | 근거 |
|------|------|------|
| 에이전트 구조 | 단일 에이전트 | Phase 간 컨텍스트 공유 빈번, Phase 3 상태 관리 단순화 |
| 데이터 전달 | 파일 기반 (`/output/*.json`) | Phase 간 데이터 크기 크고, 세션 중단 시 재개 가능성 확보 |
| 이벤트 수 결정 | 월별 평균 ±1 자동 판단 | 요청자 개입 최소화, 기존 패턴 일관성 유지 |
| Phase 3 범위 | 일정+내용+보상 전체 수정 | 요청자 최종 품질 보장, 에이전트 생성물의 오류 수정 창구 확보 |
| Sheets 출력 | API로 신규 시트 생성 | 기존 문서 오염 방지, 요청자의 2차 편집 용이성 |
