#!/usr/bin/env python3
"""
confirmed_events.json → 신규 Google Sheets 생성 (Phase 4)

서식은 raw_sheet_data.json 의 format_info 를 참조해 복제합니다.
신규 시트 이름: 이벤트기획_{대상연월}_{타임스탬프}

Usage: python write_sheet.py
Input:  output/confirmed_events.json
        output/template.json
        output/raw_sheet_data.json
Output: 신규 Sheets URL (stdout)
        output/run_log.json 갱신
"""

import json
import sys
from datetime import datetime
from pathlib import Path


CONFIRMED_PATH = Path('output/confirmed_events.json')
TEMPLATE_PATH  = Path('output/template.json')
RAW_PATH       = Path('output/raw_sheet_data.json')
LOG_PATH       = Path('output/run_log.json')


def load_inputs() -> tuple[dict, dict, dict]:
    for path in [CONFIRMED_PATH, TEMPLATE_PATH, RAW_PATH]:
        if not path.exists():
            print(f"ERROR: {path} 가 없습니다.")
            sys.exit(1)

    with open(CONFIRMED_PATH, encoding='utf-8') as f:
        confirmed = json.load(f)
    with open(TEMPLATE_PATH, encoding='utf-8') as f:
        template = json.load(f)
    with open(RAW_PATH, encoding='utf-8') as f:
        raw = json.load(f)

    return confirmed, template, raw


def get_sheets_service():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        print("ERROR: 필요한 패키지가 없습니다. pip install -r requirements.txt")
        sys.exit(1)

    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    creds = None
    token_path = Path('token.json')
    creds_path = Path('credentials.json')
    sa_path = Path('service_account.json')

    if sa_path.exists():
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_file(
            str(sa_path), scopes=SCOPES
        )
        from googleapiclient.discovery import build
        return build('sheets', 'v4', credentials=creds)

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not creds_path.exists():
                print("ERROR: credentials.json 또는 service_account.json 이 없습니다.")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'w', encoding='utf-8') as f:
            f.write(creds.to_json())

    from googleapiclient.discovery import build
    return build('sheets', 'v4', credentials=creds)


def build_spreadsheet_title(confirmed: dict) -> str:
    target = confirmed.get('target_month', 'unknown')
    ts = datetime.now().strftime('%Y%m%d_%H%M')
    return f"이벤트기획_{target}_{ts}"


def event_to_row(event: dict, columns: list[dict]) -> list[str]:
    """template.json 열 순서에 맞게 이벤트 데이터를 행으로 변환"""
    row = []
    for col in sorted(columns, key=lambda c: c['index']):
        col_name = col['name']
        row.append(str(event.get(col_name, '')))
    return row


def build_header_row(columns: list[dict]) -> list[str]:
    return [col['original_name'] for col in sorted(columns, key=lambda c: c['index'])]


def _color_to_sheets(color: dict | None) -> dict:
    """RGBA dict → Sheets API color format"""
    if not color:
        return {}
    return {
        'red':   color.get('red', 1.0),
        'green': color.get('green', 1.0),
        'blue':  color.get('blue', 1.0),
        'alpha': color.get('alpha', 1.0),
    }


def build_format_requests(sheet_id: int, format_info: dict, columns: list[dict]) -> list[dict]:
    """서식 복제를 위한 batchUpdate 요청 목록 생성"""
    requests = []
    col_count = len(columns)

    # 1) 헤더 행 배경색 + 볼드 설정
    bg_color = _color_to_sheets(format_info.get('header_background_color'))
    text_bold = format_info.get('header_text_bold', False)
    text_color = _color_to_sheets(format_info.get('header_text_color'))

    if bg_color or text_bold:
        cell_format: dict = {}
        if bg_color:
            cell_format['backgroundColor'] = bg_color
        text_fmt: dict = {'bold': text_bold}
        if text_color:
            text_fmt['foregroundColor'] = text_color
        cell_format['textFormat'] = text_fmt

        requests.append({
            'repeatCell': {
                'range': {
                    'sheetId': sheet_id,
                    'startRowIndex': 0,
                    'endRowIndex': 1,
                    'startColumnIndex': 0,
                    'endColumnIndex': col_count,
                },
                'cell': {'userEnteredFormat': cell_format},
                'fields': 'userEnteredFormat(backgroundColor,textFormat)',
            }
        })

    # 2) 헤더 행 고정
    frozen_rows = format_info.get('frozen_rows', 1)
    if frozen_rows:
        requests.append({
            'updateSheetProperties': {
                'properties': {
                    'sheetId': sheet_id,
                    'gridProperties': {'frozenRowCount': frozen_rows}
                },
                'fields': 'gridProperties.frozenRowCount',
            }
        })

    # 3) 열 너비 설정
    col_widths = format_info.get('column_widths', [])
    for i, width in enumerate(col_widths[:col_count]):
        if width and width > 0:
            requests.append({
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': sheet_id,
                        'dimension': 'COLUMNS',
                        'startIndex': i,
                        'endIndex': i + 1,
                    },
                    'properties': {'pixelSize': width},
                    'fields': 'pixelSize',
                }
            })

    return requests


def create_sheet_and_write(
    service,
    title: str,
    header_row: list[str],
    data_rows: list[list[str]],
    format_info: dict,
    columns: list[dict],
) -> str:
    """신규 Spreadsheet 생성 + 데이터 + 서식 적용, URL 반환"""

    # 1) Spreadsheet 생성
    print(f"  신규 Spreadsheet 생성: '{title}'")
    spreadsheet = service.spreadsheets().create(body={
        'properties': {'title': title},
        'sheets': [{'properties': {'title': 'Sheet1'}}]
    }).execute()

    spreadsheet_id = spreadsheet['spreadsheetId']
    sheet_id = spreadsheet['sheets'][0]['properties']['sheetId']
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"

    # 2) 데이터 쓰기 (헤더 + 이벤트 행)
    all_rows = [header_row] + data_rows
    print(f"  데이터 쓰기: 헤더 1행 + 이벤트 {len(data_rows)}행")
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range='Sheet1!A1',
        valueInputOption='USER_ENTERED',
        body={'values': all_rows}
    ).execute()

    # 3) 서식 적용
    format_requests = build_format_requests(sheet_id, format_info, columns)
    if format_requests:
        print(f"  서식 적용 ({len(format_requests)}개 규칙)")
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': format_requests}
        ).execute()

    return url


def update_run_log(phase: int, status: str, url: str | None = None, error: str | None = None):
    log = {"run_id": None, "phases": [], "escalations": []}
    if LOG_PATH.exists():
        with open(LOG_PATH, encoding='utf-8') as f:
            log = json.load(f)

    if not log.get("run_id"):
        log["run_id"] = datetime.now().isoformat()

    entry: dict = {"phase": phase, "status": status, "timestamp": datetime.now().isoformat()}
    if url:
        entry["output_url"] = url
    if error:
        entry["error"] = error

    log["phases"] = [p for p in log["phases"] if p["phase"] != phase]
    log["phases"].append(entry)

    with open(LOG_PATH, 'w', encoding='utf-8') as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def main() -> int:
    confirmed, template, raw = load_inputs()

    events = [e for e in confirmed.get('events', []) if e.get('status') == 'confirmed']
    if not events:
        print("ERROR: confirmed_events.json 에 confirmed 상태의 이벤트가 없습니다.")
        return 1

    columns: list[dict] = template.get('columns', [])
    if not columns:
        print("ERROR: template.json 에 columns 가 없습니다.")
        return 1

    format_info: dict = raw.get('format_info', {})
    title = build_spreadsheet_title(confirmed)
    header_row = build_header_row(columns)
    data_rows = [event_to_row(ev, columns) for ev in events]

    service = get_sheets_service()

    max_retries = 3
    url = None
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            print(f"[Phase 4] Sheets 생성 시도 {attempt}/{max_retries}")
            url = create_sheet_and_write(service, title, header_row, data_rows, format_info, columns)
            break
        except Exception as e:
            last_error = str(e)
            print(f"  오류 (시도 {attempt}): {e}")
            if attempt == max_retries:
                update_run_log(4, "failed", error=last_error)
                print(f"\n[에스컬레이션] Phase 4 에서 {max_retries}회 모두 실패했습니다.")
                print(f"원인: {last_error}")
                print("해결 방법: Google API 권한 및 네트워크 상태를 확인해주세요.")
                return 1

    update_run_log(4, "success", url=url)

    print(f"\n완료!")
    print(f"신규 Google Sheets: {url}")
    print(f"시트 이름: {title}")
    print(f"이벤트 수: {len(events)}개")

    return 0


if __name__ == '__main__':
    sys.exit(main())
