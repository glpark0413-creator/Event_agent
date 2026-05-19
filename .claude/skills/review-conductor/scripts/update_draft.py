#!/usr/bin/env python3
"""
Phase 3 이벤트 초안 수정 유틸리티

Claude(CLAUDE.md)가 사용자 응답을 해석한 후 이 스크립트를 통해 JSON을 갱신합니다.

Usage:
  # 특정 필드 수정
  python update_draft.py --event-id 1 --field 종료일 --value "2025/05/06"

  # 이벤트 상태 확정
  python update_draft.py --event-id 1 --confirm

  # 이벤트 삭제
  python update_draft.py --delete-id 2

  # 새 이벤트 추가 (JSON 문자열)
  python update_draft.py --add '{"이벤트명":"...", "카테고리":"미션", ...}'

  # 전체 초기화 (다시 검토)
  python update_draft.py --reset-all

Input/Output: output/confirmed_events.json (없으면 output/draft_events.json 에서 복사)
"""

import argparse
import json
import shutil
import sys
from pathlib import Path


DRAFT_PATH = Path('output/draft_events.json')
CONFIRMED_PATH = Path('output/confirmed_events.json')


def load_draft() -> dict:
    """confirmed_events.json 우선, 없으면 draft_events.json 에서 복사"""
    if CONFIRMED_PATH.exists():
        with open(CONFIRMED_PATH, encoding='utf-8') as f:
            return json.load(f)
    if DRAFT_PATH.exists():
        shutil.copy(DRAFT_PATH, CONFIRMED_PATH)
        with open(CONFIRMED_PATH, encoding='utf-8') as f:
            return json.load(f)
    print("ERROR: output/draft_events.json 또는 output/confirmed_events.json 이 없습니다.")
    sys.exit(1)


def save_draft(data: dict):
    with open(CONFIRMED_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # 진행 상태 갱신
    confirmed_count = sum(1 for e in data.get('events', []) if e.get('status') == 'confirmed')
    data.setdefault('review_progress', {})
    data['review_progress']['confirmed'] = confirmed_count
    data['review_progress']['total'] = len(data.get('events', []))
    with open(CONFIRMED_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def find_event(events: list[dict], event_id: int) -> tuple[int, dict] | tuple[None, None]:
    for i, ev in enumerate(events):
        if ev.get('id') == event_id:
            return i, ev
    return None, None


def cmd_update_field(data: dict, event_id: int, field: str, value: str):
    idx, ev = find_event(data['events'], event_id)
    if idx is None:
        print(f"ERROR: id={event_id} 인 이벤트를 찾을 수 없습니다.")
        sys.exit(1)
    old_value = ev.get(field, '(없음)')
    data['events'][idx][field] = value
    print(f"  [id={event_id}] {field}: '{old_value}' → '{value}'")
    save_draft(data)


def cmd_confirm(data: dict, event_id: int):
    idx, ev = find_event(data['events'], event_id)
    if idx is None:
        print(f"ERROR: id={event_id} 인 이벤트를 찾을 수 없습니다.")
        sys.exit(1)
    data['events'][idx]['status'] = 'confirmed'
    save_draft(data)
    confirmed = sum(1 for e in data['events'] if e.get('status') == 'confirmed')
    total = len(data['events'])
    print(f"  [id={event_id}] 확정 완료 ({confirmed}/{total})")


def cmd_delete(data: dict, event_id: int):
    events = data.get('events', [])
    before = len(events)
    data['events'] = [e for e in events if e.get('id') != event_id]
    after = len(data['events'])
    if before == after:
        print(f"ERROR: id={event_id} 인 이벤트를 찾을 수 없습니다.")
        sys.exit(1)
    # id 재부여하지 않음 (순서 추적용 원래 id 유지)
    save_draft(data)
    print(f"  [id={event_id}] 삭제 완료 (남은 이벤트: {after}개)")


def cmd_add(data: dict, event_json: str):
    try:
        new_event = json.loads(event_json)
    except json.JSONDecodeError as e:
        print(f"ERROR: JSON 파싱 오류: {e}")
        sys.exit(1)

    events = data.get('events', [])
    max_id = max((e.get('id', 0) for e in events), default=0)
    new_event['id'] = max_id + 1
    new_event.setdefault('status', 'pending')
    data.setdefault('events', []).append(new_event)
    save_draft(data)
    print(f"  [id={new_event['id']}] 신규 이벤트 추가: {new_event.get('이벤트명', '(이름 없음)')}")
    print(f"  전체 이벤트: {len(data['events'])}개")


def cmd_reset_all(data: dict):
    for ev in data.get('events', []):
        ev['status'] = 'pending'
    data['review_progress'] = {'confirmed': 0, 'total': len(data.get('events', []))}
    save_draft(data)
    print(f"  전체 {len(data['events'])}개 이벤트 상태 초기화 완료")


def main() -> int:
    parser = argparse.ArgumentParser(description='Phase 3 이벤트 초안 수정')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--confirm', action='store_true', help='이벤트 확정')
    group.add_argument('--field', help='수정할 필드 이름')
    group.add_argument('--delete-id', type=int, metavar='ID', help='이벤트 삭제')
    group.add_argument('--add', metavar='JSON', help='신규 이벤트 추가 (JSON 문자열)')
    group.add_argument('--reset-all', action='store_true', help='전체 상태 초기화')

    parser.add_argument('--event-id', type=int, help='대상 이벤트 id (--confirm, --field 에 필요)')
    parser.add_argument('--value', help='수정할 값 (--field 에 필요)')

    args = parser.parse_args()

    data = load_draft()

    if args.confirm:
        if not args.event_id:
            print("ERROR: --confirm 에는 --event-id 가 필요합니다.")
            return 1
        cmd_confirm(data, args.event_id)

    elif args.field:
        if not args.event_id:
            print("ERROR: --field 에는 --event-id 가 필요합니다.")
            return 1
        if args.value is None:
            print("ERROR: --field 에는 --value 가 필요합니다.")
            return 1
        cmd_update_field(data, args.event_id, args.field, args.value)

    elif args.delete_id is not None:
        cmd_delete(data, args.delete_id)

    elif args.add:
        cmd_add(data, args.add)

    elif args.reset_all:
        cmd_reset_all(data)

    return 0


if __name__ == '__main__':
    sys.exit(main())
