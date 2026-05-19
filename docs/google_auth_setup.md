# Google API 인증 설정 가이드

에이전트는 Google Sheets API v4를 사용합니다.
두 가지 인증 방식 중 하나를 선택해 설정하세요.

---

## 방법 A. OAuth 2.0 (개인 Google 계정 — 권장)

### 1. Google Cloud 프로젝트 생성
1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 상단 프로젝트 선택 → **새 프로젝트** 생성

### 2. Google Sheets API 활성화
1. **API 및 서비스 → 라이브러리** 이동
2. "Google Sheets API" 검색 → **사용 설정**

### 3. OAuth 2.0 클라이언트 ID 생성
1. **API 및 서비스 → 사용자 인증 정보** 이동
2. **+ 사용자 인증 정보 만들기 → OAuth 클라이언트 ID** 클릭
3. 애플리케이션 유형: **데스크톱 앱** 선택
4. 이름 입력 후 **만들기**
5. **JSON 다운로드** → 프로젝트 루트에 `credentials.json` 으로 저장

### 4. OAuth 동의 화면 설정 (최초 1회)
1. **OAuth 동의 화면** 이동
2. 사용자 유형: **외부** (또는 내부, 조직에 따라)
3. 앱 이름, 이메일 입력 후 저장
4. **테스트 사용자** 탭에서 본인 이메일 추가

### 5. 첫 실행 (브라우저 인증)
```bash
python .claude/skills/sheets-reader/scripts/read_sheet.py --url "<URL>"
```
- 브라우저가 자동으로 열리고 Google 로그인 화면 표시
- 계정 선택 → 권한 허용
- 완료 후 `token.json` 이 프로젝트 루트에 생성됨 (이후 재인증 불필요)

> ⚠️ `token.json` 은 Git에 올리지 마세요. `.gitignore` 에 추가하세요.

---

## 방법 B. 서비스 계정 (자동화 서버 환경)

### 1~2 단계는 방법 A와 동일

### 3. 서비스 계정 생성
1. **API 및 서비스 → 사용자 인증 정보** 이동
2. **+ 사용자 인증 정보 만들기 → 서비스 계정** 클릭
3. 이름 입력 → **만들기 및 계속**
4. 역할: **편집자** 또는 **소유자** 선택 → 완료

### 4. 키 파일 다운로드
1. 생성된 서비스 계정 클릭
2. **키 탭 → 키 추가 → JSON** 다운로드
3. 프로젝트 루트에 `service_account.json` 으로 저장

### 5. 기존 Sheets 공유 설정
- 기존 이벤트 Sheets를 서비스 계정 이메일(`...@...iam.gserviceaccount.com`)에 **뷰어** 권한으로 공유

> ⚠️ 서비스 계정으로 생성한 신규 Sheets는 서비스 계정 소유로 생성됩니다.
> 본인 드라이브에서 확인하려면 해당 Sheets를 본인 계정과 공유하세요.

---

## 인증 우선순위

에이전트는 다음 순서로 인증 파일을 탐색합니다:

1. `service_account.json` — 있으면 우선 사용 (브라우저 불필요)
2. `token.json` — 캐시된 OAuth 토큰 재사용
3. `credentials.json` — 첫 실행 시 브라우저 인증 흐름 진행

---

## 파일 구조 확인

```
event-planner-agent/
  ├── credentials.json       # OAuth 클라이언트 (방법 A)
  ├── token.json             # 자동 생성, 재인증 토큰 (방법 A)
  ├── service_account.json   # 서비스 계정 키 (방법 B)
  └── ...
```

---

## 필요 패키지 설치

```bash
pip install -r requirements.txt
```

---

## 문제 해결

| 오류 | 원인 | 해결 방법 |
|---|---|---|
| `credentials.json not found` | 키 파일 없음 | 위 가이드 3번 단계 수행 |
| `403 Forbidden` | API 미활성화 | Cloud Console에서 Sheets API 활성화 |
| `400 redirect_uri_mismatch` | OAuth 설정 오류 | 애플리케이션 유형을 '데스크톱 앱'으로 설정 |
| `HttpError 429` | API 할당량 초과 | 잠시 후 재시도 |
| 서비스 계정 Sheets 조회 안 됨 | 공유 권한 없음 | 기존 Sheets에 서비스 계정 이메일을 공유 |
