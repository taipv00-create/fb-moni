"""Đẩy toàn bộ data/*.json hiện có lên Supabase.

Cách dùng:
    1. Mở Supabase Studio → SQL Editor → chạy file `supabase_schema.sql`
    2. Đảm bảo `.env` có SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY
    3. python migrate_to_supabase.py
"""

import json
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from core import supabase_store as sb

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, 'data')


def _read(name, default):
    path = os.path.join(DATA, name)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def main():
    if not sb.is_enabled():
        print('[migrate] SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY chưa được set trong .env')
        sys.exit(1)

    ping = sb.ping()
    if not ping.get('ok'):
        print(f'[migrate] Không kết nối được Supabase: {ping}')
        sys.exit(1)
    print(f'[migrate] Kết nối Supabase OK ({ping})')

    groups = _read('groups.json', [])
    for g in groups:
        sb.upsert_group(g.get('id', ''), g.get('name', ''))
    print(f'[migrate] groups: {len(groups)}')

    tg_cfg = _read('telegram_config.json', {})
    chat_ids = tg_cfg.get('chat_ids') or ([tg_cfg['chat_id']] if tg_cfg.get('chat_id') else [])
    for cid in chat_ids:
        sb.add_chat_id(cid)
    print(f'[migrate] telegram_chat_ids: {len(chat_ids)}')

    settings = _read('settings.json', None)
    if settings is not None:
        sb.kv_set('settings', settings)
        print('[migrate] settings: ok')

    ai_cfg = _read('ai_config.json', None)
    if ai_cfg is not None:
        sb.kv_set('ai_config', ai_cfg)
        print('[migrate] ai_config: ok')

    seen = _read('seen_posts.json', [])
    sb.add_seen_post_ids(seen)
    print(f'[migrate] seen_posts: {len(seen)}')

    classifications = _read('classifications.json', {})
    sb.upsert_classifications(classifications)
    print(f'[migrate] classifications: {len(classifications)}')

    print('[migrate] DONE')


if __name__ == '__main__':
    main()
