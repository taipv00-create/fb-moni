import os
import json
import threading
import re
import uuid
import hashlib
import secrets
import requests as _req
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session
from flask_cors import CORS

from core.group_api import FacebookGroupAPI, load_token, load_cookie, refresh_token
from core.ai_classifier import AIClassifier, DEFAULT_MODEL, DEFAULT_API_KEY, DEFAULT_CATEGORIES, PROVIDERS
from core import supabase_store as sb

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
load_dotenv(os.path.join(BASE_DIR, '.env'))

SEEN_FILE = os.path.join(DATA_DIR, 'seen_posts.json')
TG_CONFIG_FILE = os.path.join(DATA_DIR, 'telegram_config.json')
GROUPS_FILE = os.path.join(DATA_DIR, 'groups.json')
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')
AI_CONFIG_FILE = os.path.join(DATA_DIR, 'ai_config.json')
CLASSIFICATIONS_FILE = os.path.join(DATA_DIR, 'classifications.json')
LEADS_FILE = os.path.join(DATA_DIR, 'leads.json')
REPLY_SUGGESTIONS_FILE = os.path.join(DATA_DIR, 'reply_suggestions.json')
BUSINESS_PROFILE_FILE = os.path.join(DATA_DIR, 'business_profile.json')
STAFF_COOKIES_FILE = os.path.join(DATA_DIR, 'staff_cookies.json')
STAFF_TOKEN_DIR = os.path.join(DATA_DIR, 'staff_tokens')
COMMENT_LOGS_FILE = os.path.join(DATA_DIR, 'comment_logs.json')

BOT_TOKEN = os.environ.get('TG_BOT_TOKEN', '8724375632:AAEgyz4yRPivDYWGXesTaJHhdqWYIraSoT8')
DEFAULT_GROUP = os.environ.get('DEFAULT_GROUP', '3809441172650624')
PORT = int(os.environ.get('PORT', 5000))
WEB_UI_URL = (os.environ.get('WEB_UI_URL') or 'http://localhost:3000').rstrip('/')
USE_LEGACY_UI = os.environ.get('USE_LEGACY_UI', '').lower() in ('1', 'true', 'yes')
SUPABASE_URL = os.environ.get('SUPABASE_URL') or os.environ.get('VITE_SUPABASE_URL', '')
SUPABASE_KEY = (
    os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    or os.environ.get('SUPABASE_PUBLISHABLE_KEY')
    or os.environ.get('VITE_SUPABASE_PUBLISHABLE_KEY', '')
)
SUPABASE_REPLY_TABLE = os.environ.get('SUPABASE_REPLY_TABLE', 'ai_reply_suggestions')
SUPABASE_PROFILE_TABLE = os.environ.get('SUPABASE_PROFILE_TABLE', 'business_profiles')
SUPABASE_COMMENT_LOG_TABLE = os.environ.get('SUPABASE_COMMENT_LOG_TABLE', 'comment_logs')
APP_TIMEZONE = os.environ.get('APP_TIMEZONE', 'Asia/Ho_Chi_Minh')

app = Flask(__name__, template_folder='views')
app.secret_key = os.environ.get('APP_SECRET_KEY', 'fb-moni-local-dev-secret-change-me')

_cors_origins = [
    o.strip()
    for o in os.environ.get(
        'CORS_ORIGINS',
        'http://localhost:3000,http://127.0.0.1:3000',
    ).split(',')
    if o.strip()
]
CORS(app, resources={r'/api/*': {'origins': _cors_origins}})

# ── State ──────────────────────────────────────────────
_api_cache: dict = {}
_seen_ids: set = set()
_tg_chat_ids: list = []
_pages_cache: dict = {}  # {page_id: {name, access_token}}
_groups: list = []       # [{id, name}]
_settings: dict = {}    # {auto_refresh, interval}
_ai_config: dict = {}   # {provider, model, keys, auto_classify, categories}
_classifications: dict = {}  # {post_id: category}
_leads: dict = {}       # {post_id: [lead]}
_reply_suggestions: dict = {}  # {post_id: latest suggestion}
_business_profile: dict = {}  # {business_name, phone, address, why_choose_us, extra_notes}
_staff_cookies: dict = {}  # {active_staff_id, staff: [{id, name, cookie, enabled}]}
_comment_logs: list = []


def _default_business_profile() -> dict:
    return {
        'business_name': '',
        'phone': '',
        'address': '',
        'why_choose_us': '',
        'extra_notes': '',
    }


USE_SUPABASE = sb.is_enabled()


def _read_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def _write_json(path, data):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def _default_ai_config():
    return {
        'provider': 'gemini',
        'model': DEFAULT_MODEL,
        'keys': {'gemini': DEFAULT_API_KEY, 'openai': '', 'claude': ''},
        'auto_classify': False,
        'categories': DEFAULT_CATEGORIES,
    }


def _default_staff_cookies() -> dict:
    return {'active_staff_id': '', 'staff': []}


def _hash_password(password: str, salt: str = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 120000)
    return salt, digest.hex()


def _verify_password(password: str, salt: str, digest: str) -> bool:
    if not password or not salt or not digest:
        return False
    _, candidate = _hash_password(password, salt)
    return secrets.compare_digest(candidate, digest)


def _load_state():
    global _seen_ids, _tg_chat_ids, _groups, _settings, _ai_config, _classifications, _leads, _reply_suggestions, _business_profile, _staff_cookies, _comment_logs
    os.makedirs(DATA_DIR, exist_ok=True)

    loaded_from_supabase = False
    if USE_SUPABASE:
        try:
            _seen_ids = set(sb.list_seen_post_ids())
            _tg_chat_ids = sb.list_chat_ids() or ['7129448686']
            _groups = sb.list_groups() or [{'id': DEFAULT_GROUP, 'name': ''}]
            _settings = sb.kv_get('settings', None) or {'auto_refresh': True, 'interval': 5}
            _ai_config = sb.kv_get('ai_config', None) or _default_ai_config()
            _classifications = sb.list_classifications()
            _leads = _read_json(LEADS_FILE, {})
            _reply_suggestions = _read_json(REPLY_SUGGESTIONS_FILE, {})
            loaded_profile = _read_json(BUSINESS_PROFILE_FILE, {})
            _business_profile = {**_default_business_profile(), **loaded_profile}
            profile_sb, _ = _load_business_profile_from_supabase()
            if profile_sb:
                _business_profile = {**_business_profile, **profile_sb}
            print('[supabase] state loaded from Supabase')
            loaded_from_supabase = True
        except Exception as e:
            print(f'[supabase] load failed, fallback file: {e}')

    if not loaded_from_supabase:
        _seen_ids = set(_read_json(SEEN_FILE, []))
        cfg = _read_json(TG_CONFIG_FILE, {})
        _tg_chat_ids = cfg.get('chat_ids') or ([cfg['chat_id']] if cfg.get('chat_id') else ['7129448686'])
        _groups = _read_json(GROUPS_FILE, [{'id': DEFAULT_GROUP, 'name': ''}])
        _settings = _read_json(SETTINGS_FILE, {'auto_refresh': True, 'interval': 5})
        _ai_config = _read_json(AI_CONFIG_FILE, _default_ai_config())
        _classifications = _read_json(CLASSIFICATIONS_FILE, {})
        _leads = _read_json(LEADS_FILE, {})
        _reply_suggestions = _read_json(REPLY_SUGGESTIONS_FILE, {})
        loaded_profile = _read_json(BUSINESS_PROFILE_FILE, {})
        _business_profile = {**_default_business_profile(), **loaded_profile}

    loaded_staff = _read_json(STAFF_COOKIES_FILE, _default_staff_cookies())
    _staff_cookies = {**_default_staff_cookies(), **loaded_staff}
    if not isinstance(_staff_cookies.get('staff'), list):
        _staff_cookies['staff'] = []
    changed_staff = False
    for item in _staff_cookies['staff']:
        if 'role' not in item:
            item['role'] = 'staff'
            changed_staff = True
        if 'username' not in item:
            item['username'] = re.sub(r'\W+', '_', (item.get('name') or item.get('id') or '')).strip('_').lower()
            changed_staff = True
    if _staff_cookies['staff'] and not any(item.get('role') == 'admin' for item in _staff_cookies['staff']):
        _staff_cookies['staff'][0]['role'] = 'admin'
        changed_staff = True
    if changed_staff:
        _save_staff_cookies()

    _comment_logs = _read_json(COMMENT_LOGS_FILE, [])
    if not isinstance(_comment_logs, list):
        _comment_logs = []


def _save_seen(new_posts=None):
    """Lưu file seen_posts.json và đẩy metadata bài viết mới lên Supabase.

    `new_posts` là list dict bài mới (đã có `_group_id`, `permalink_url`...).
    """
    _write_json(SEEN_FILE, list(_seen_ids))
    if USE_SUPABASE and new_posts:
        try:
            sb.upsert_posts(new_posts)
        except Exception as e:
            print(f'[supabase] save_seen failed: {e}')


def _save_tg():
    _write_json(TG_CONFIG_FILE, {'chat_ids': _tg_chat_ids})


def _save_groups():
    _write_json(GROUPS_FILE, _groups)


def _save_settings():
    _write_json(SETTINGS_FILE, _settings)
    if USE_SUPABASE:
        try:
            sb.kv_set('settings', _settings)
        except Exception as e:
            print(f'[supabase] save_settings failed: {e}')


def _save_ai_config():
    _write_json(AI_CONFIG_FILE, _ai_config)
    if USE_SUPABASE:
        try:
            sb.kv_set('ai_config', _ai_config)
        except Exception as e:
            print(f'[supabase] save_ai_config failed: {e}')


def _save_classifications(new_items=None):
    _write_json(CLASSIFICATIONS_FILE, _classifications)
    if USE_SUPABASE and new_items:
        try:
            sb.upsert_classifications(new_items)
        except Exception as e:
            print(f'[supabase] save_classifications failed: {e}')


def _save_leads():
    with open(LEADS_FILE, 'w', encoding='utf-8') as f:
        json.dump(_leads, f, ensure_ascii=False)


def _save_reply_suggestions():
    with open(REPLY_SUGGESTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(_reply_suggestions, f, ensure_ascii=False)


def _save_staff_cookies():
    with open(STAFF_COOKIES_FILE, 'w') as f:
        json.dump(_staff_cookies, f, ensure_ascii=False)


def _save_comment_logs():
    with open(COMMENT_LOGS_FILE, 'w') as f:
        json.dump(_comment_logs[-1000:], f, ensure_ascii=False)


def _extract_cookie_user(cookie: str) -> str:
    match = re.search(r'(?:^|;\s*)c_user=([^;]+)', cookie or '')
    return match.group(1) if match else ''


def _mask_cookie(cookie: str) -> str:
    if not cookie:
        return ''
    c_user = _extract_cookie_user(cookie)
    if c_user:
        return f'c_user={c_user}; ...'
    return cookie[:8] + '...' + cookie[-6:] if len(cookie) > 18 else '***'


def _public_staff_cookie(row: dict) -> dict:
    cookie = row.get('cookie', '')
    return {
        'id': row.get('id', ''),
        'name': row.get('name', ''),
        'username': row.get('username', ''),
        'role': row.get('role', 'staff'),
        'cookie_masked': _mask_cookie(cookie),
        'facebook_user_id': _extract_cookie_user(cookie),
        'enabled': bool(row.get('enabled', True)),
        'created_at': row.get('created_at', ''),
        'updated_at': row.get('updated_at', ''),
    }


def _staff_accounts() -> list:
    return _staff_cookies.get('staff') or []


def _setup_required() -> bool:
    return not any(item.get('enabled', True) and item.get('username') and item.get('password_hash') for item in _staff_accounts())


def _current_staff() -> dict:
    staff_id = session.get('staff_id', '')
    if not staff_id:
        return {}
    return next((item for item in _staff_accounts() if item.get('id') == staff_id and item.get('enabled', True)), {})


def _current_staff_id() -> str:
    return _current_staff().get('id', '')


def _is_admin() -> bool:
    return _current_staff().get('role') == 'admin'


def _public_current_staff() -> dict:
    staff = _current_staff()
    return _public_staff_cookie(staff) if staff else {}


def _active_staff() -> dict:
    current = _current_staff()
    if current:
        return current
    if _setup_required():
        return {}
    active_id = _staff_cookies.get('active_staff_id', '')
    active = next((item for item in _staff_accounts() if item.get('id') == active_id and item.get('enabled', True)), None)
    return active or {}


def _active_staff_id() -> str:
    return _active_staff().get('id', '')


def _active_cookie() -> str:
    return _active_staff().get('cookie', '')


def _staff_token_file(staff_id: str) -> str:
    safe_id = re.sub(r'[^a-zA-Z0-9_-]+', '_', staff_id or 'default')
    return os.path.join(STAFF_TOKEN_DIR, f'{safe_id}.txt')


def _invalidate_facebook_cache():
    _api_cache.clear()
    _pages_cache.clear()


def _clean_business_profile(body: dict) -> dict:
    current = {**_default_business_profile(), **(_business_profile or {})}
    limits = {
        'business_name': 120,
        'phone': 60,
        'address': 240,
        'why_choose_us': 1000,
        'extra_notes': 800,
    }
    for key, limit in limits.items():
        if key in body:
            current[key] = str(body.get(key) or '').strip()[:limit]
    return current


def _save_business_profile():
    tmp = BUSINESS_PROFILE_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(_business_profile, f, ensure_ascii=False)
    os.replace(tmp, BUSINESS_PROFILE_FILE)


def _load_business_profile_from_supabase() -> tuple[dict, str]:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {}, 'Chưa cấu hình Supabase'
    try:
        resp = _req.get(
            f"{SUPABASE_URL.rstrip('/')}/rest/v1/{SUPABASE_PROFILE_TABLE}",
            headers={
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
            },
            params={'id': 'eq.default', 'select': '*', 'limit': '1'},
            timeout=20,
        )
        if resp.status_code != 200:
            return {}, resp.text[:300]
        rows = resp.json()
        if not rows:
            return {}, ''
        row = rows[0]
        return {
            'business_name': row.get('business_name') or '',
            'phone': row.get('phone') or '',
            'address': row.get('address') or '',
            'why_choose_us': row.get('why_choose_us') or '',
            'extra_notes': row.get('extra_notes') or '',
        }, ''
    except Exception as e:
        return {}, str(e)[:300]


def _save_business_profile_to_supabase(profile: dict) -> tuple[bool, str]:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False, 'Chưa cấu hình Supabase'
    payload = {
        'id': 'default',
        'business_name': profile.get('business_name', ''),
        'phone': profile.get('phone', ''),
        'address': profile.get('address', ''),
        'why_choose_us': profile.get('why_choose_us', ''),
        'extra_notes': profile.get('extra_notes', ''),
    }
    try:
        resp = _req.post(
            f"{SUPABASE_URL.rstrip('/')}/rest/v1/{SUPABASE_PROFILE_TABLE}",
            headers={
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
                'Content-Type': 'application/json',
                'Prefer': 'resolution=merge-duplicates,return=representation',
            },
            params={'on_conflict': 'id'},
            json=payload,
            timeout=20,
        )
        if resp.status_code in (200, 201):
            return True, ''
        return False, (resp.json().get('message') if resp.headers.get('content-type', '').startswith('application/json') else resp.text)[:300]
    except Exception as e:
        return False, str(e)[:300]


def _save_reply_suggestion_to_supabase(suggestion: dict) -> tuple[bool, str]:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False, 'Chưa cấu hình Supabase'
    payload = {
        'post_id': suggestion.get('post_id', ''),
        'group_id': suggestion.get('group_id', ''),
        'post_url': suggestion.get('post_url', ''),
        'target_source': suggestion.get('target_source', ''),
        'target_source_id': suggestion.get('target_source_id', ''),
        'customer_name': suggestion.get('customer_name', ''),
        'intent_label': suggestion.get('intent_label', ''),
        'customer_need': suggestion.get('customer_need', ''),
        'buying_stage': suggestion.get('buying_stage', ''),
        'urgency': suggestion.get('urgency', ''),
        'confidence': suggestion.get('confidence', 0),
        'recommended_approach': suggestion.get('recommended_approach', ''),
        'suggested_replies': suggestion.get('suggested_replies', []),
        'raw_ai': suggestion,
    }
    try:
        resp = _req.post(
            f"{SUPABASE_URL.rstrip('/')}/rest/v1/{SUPABASE_REPLY_TABLE}",
            headers={
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
                'Content-Type': 'application/json',
                'Prefer': 'return=minimal',
            },
            json=payload,
            timeout=20,
        )
        if resp.status_code in (200, 201, 204):
            return True, ''
        return False, (resp.json().get('message') if resp.headers.get('content-type', '').startswith('application/json') else resp.text)[:300]
    except Exception as e:
        return False, str(e)[:300]


def _save_comment_log_to_supabase(log: dict) -> tuple[bool, str]:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False, 'Chưa cấu hình Supabase'
    payload = {
        'staff_id': log.get('staff_id', ''),
        'staff_name': log.get('staff_name', ''),
        'staff_username': log.get('staff_username', ''),
        'facebook_user_id': log.get('facebook_user_id', ''),
        'post_id': log.get('post_id', ''),
        'group_id': log.get('group_id', ''),
        'post_url': log.get('post_url', ''),
        'comment_text': log.get('comment_text', ''),
        'comment_id': log.get('comment_id', ''),
        'page_id': log.get('page_id', ''),
        'status': log.get('status', ''),
        'error_message': log.get('error_message', ''),
        'created_at': log.get('created_at'),
    }
    try:
        resp = _req.post(
            f"{SUPABASE_URL.rstrip('/')}/rest/v1/{SUPABASE_COMMENT_LOG_TABLE}",
            headers={
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
                'Content-Type': 'application/json',
                'Prefer': 'return=minimal',
            },
            json=payload,
            timeout=20,
        )
        if resp.status_code in (200, 201, 204):
            return True, ''
        return False, (resp.json().get('message') if resp.headers.get('content-type', '').startswith('application/json') else resp.text)[:300]
    except Exception as e:
        return False, str(e)[:300]


def _record_comment_log(post_id: str, group_id: str, post_url: str, message: str, page_id: str,
                        status: str, comment_id: str = '', error_message: str = '') -> dict:
    global _comment_logs
    staff = _current_staff()
    now = datetime.utcnow().isoformat(timespec='seconds') + 'Z'
    log = {
        'staff_id': staff.get('id', ''),
        'staff_name': staff.get('name', ''),
        'staff_username': staff.get('username', ''),
        'facebook_user_id': _extract_cookie_user(staff.get('cookie', '')),
        'post_id': post_id,
        'group_id': group_id,
        'post_url': post_url,
        'comment_text': message,
        'comment_id': comment_id,
        'page_id': page_id,
        'status': status,
        'error_message': error_message,
        'created_at': now,
    }
    _comment_logs.append(log)
    _save_comment_logs()
    supabase_ok, supabase_error = _save_comment_log_to_supabase(log)
    log['storage'] = 'supabase' if supabase_ok else 'local'
    if supabase_error:
        log['storage_warning'] = supabase_error
    return log


def _today_utc_bounds() -> tuple[datetime, datetime]:
    try:
        tz = ZoneInfo(APP_TIMEZONE)
    except Exception:
        tz = ZoneInfo('Asia/Ho_Chi_Minh')
    today = datetime.now(tz).date()
    start_local = datetime.combine(today, time.min, tzinfo=tz)
    end_local = datetime.combine(today, time.max, tzinfo=tz)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _parse_log_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
    except Exception:
        return None


def _count_today_success_local(staff_id: str = '') -> int:
    start_utc, end_utc = _today_utc_bounds()
    count = 0
    for item in _comment_logs:
        if item.get('status') != 'success':
            continue
        if staff_id and item.get('staff_id') != staff_id:
            continue
        created_at = _parse_log_time(item.get('created_at', ''))
        if created_at and start_utc <= created_at <= end_utc:
            count += 1
    return count


def _count_today_success_supabase(staff_id: str = '') -> tuple[int | None, str]:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None, 'Chưa cấu hình Supabase'
    start_utc, end_utc = _today_utc_bounds()
    params = [
        ('select', 'id'),
        ('status', 'eq.success'),
        ('created_at', f'gte.{start_utc.isoformat()}'),
        ('created_at', f'lte.{end_utc.isoformat()}'),
    ]
    if staff_id:
        params.append(('staff_id', f'eq.{staff_id}'))
    try:
        resp = _req.get(
            f"{SUPABASE_URL.rstrip('/')}/rest/v1/{SUPABASE_COMMENT_LOG_TABLE}",
            headers={
                'apikey': SUPABASE_KEY,
                'Authorization': f'Bearer {SUPABASE_KEY}',
                'Prefer': 'count=exact',
                'Range': '0-0',
            },
            params=params,
            timeout=20,
        )
        if resp.status_code not in (200, 206):
            return None, resp.text[:300]
        content_range = resp.headers.get('content-range') or resp.headers.get('Content-Range') or ''
        if '/' in content_range:
            return int(content_range.rsplit('/', 1)[-1]), ''
        return len(resp.json()), ''
    except Exception as e:
        return None, str(e)[:300]


def _get_ai_key(provider: str) -> str:
    stored_key = (_ai_config.get('keys') or {}).get(provider, '')
    env_keys = {
        'gemini': 'GEMINI_API_KEY',
        'openai': 'OPENAI_API_KEY',
        'claude': 'CLAUDE_API_KEY',
    }
    return stored_key or os.environ.get(env_keys.get(provider, ''), '') or DEFAULT_API_KEY


def _get_classifier() -> AIClassifier:
    provider = _ai_config.get('provider', 'gemini')
    default_model = PROVIDERS.get(provider, {}).get('default_model', DEFAULT_MODEL)
    model = _ai_config.get('model', default_model) or default_model
    api_key = _get_ai_key(provider)
    categories = _ai_config.get('categories', DEFAULT_CATEGORIES)
    return AIClassifier(provider, model, api_key, categories)


def get_api(group_id: str) -> FacebookGroupAPI:
    staff_id = _active_staff_id()
    cache_key = f'{staff_id or "default"}:{group_id}'
    if cache_key not in _api_cache:
        token_file = _staff_token_file(staff_id) if staff_id else None
        _api_cache[cache_key] = FacebookGroupAPI(group_id, cookie=_active_cookie(), token_file=token_file)
    return _api_cache[cache_key]


@app.before_request
def _require_auth_for_api():
    public_endpoints = {'auth_status', 'auth_login', 'auth_setup'}
    if request.path.startswith('/api/') and request.endpoint not in public_endpoints:
        if _setup_required():
            return jsonify({'ok': False, 'error': 'Cần setup tài khoản đầu tiên', 'setup_required': True}), 401
        if not _current_staff():
            return jsonify({'ok': False, 'error': 'Vui lòng đăng nhập', 'auth_required': True}), 401


# ── Telegram ───────────────────────────────────────────
def _tg_send(chat_id: str, text: str):
    try:
        _req.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
            json={'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown',
                  'disable_web_page_preview': False},
            timeout=10,
        )
    except Exception:
        pass


def _notify_new_post(post: dict):
    if not _tg_chat_ids:
        return
    author = (post.get('from') or {}).get('name', 'Ẩn danh')
    text = post.get('message', '') or ''
    preview = text[:300] + ('...' if len(text) > 300 else '')
    msg = (
        f"🔔 *Bài mới trong nhóm* `{post.get('_group_id', '')}`\n\n"
        f"👤 *{author}*\n{preview}\n\n"
        f"[🔗 Xem bài viết]({post.get('permalink_url', '')})"
    )
    for cid in _tg_chat_ids:
        _tg_send(cid, msg)


def _poll_telegram():
    offset = 0
    while True:
        try:
            r = _req.get(
                f'https://api.telegram.org/bot{BOT_TOKEN}/getUpdates',
                params={'offset': offset, 'timeout': 30},
                timeout=35,
            )
            for upd in r.json().get('result', []):
                offset = upd['update_id'] + 1
                msg = upd.get('message', {})
                if msg.get('text', '').startswith('/start'):
                    cid = str(msg['chat']['id'])
                    name = msg['from'].get('first_name', '')
                    _tg_send(cid,
                        f"👋 Xin chào {name}\\!\n\n"
                        f"Chat ID của bạn là:\n`{cid}`\n\n"
                        f"Copy ID này rồi vào web thêm vào mục *Telegram* để nhận thông báo\\."
                    )
        except Exception:
            pass


# ── Routes ─────────────────────────────────────────────
@app.route('/')
def index():
    if USE_LEGACY_UI:
        return render_template('index.html')
    from flask import redirect
    return redirect(WEB_UI_URL)


@app.route('/api/auth/status')
def auth_status():
    staff = _public_current_staff()
    return jsonify({
        'ok': True,
        'authenticated': bool(staff),
        'setup_required': _setup_required(),
        'staff': staff,
    })


@app.route('/api/auth/setup', methods=['POST'])
def auth_setup():
    global _staff_cookies
    if not _setup_required():
        return jsonify({'ok': False, 'error': 'Hệ thống đã setup tài khoản đầu tiên'}), 400
    body = request.get_json() or {}
    name = str(body.get('name') or '').strip()[:80]
    username = str(body.get('username') or '').strip().lower()[:60]
    password = str(body.get('password') or '')
    cookie = str(body.get('cookie') or '').strip()
    if not name or not username or not password or not cookie:
        return jsonify({'ok': False, 'error': 'Nhập đủ tên, tài khoản, mật khẩu và cookie'}), 400
    if len(password) < 6:
        return jsonify({'ok': False, 'error': 'Mật khẩu tối thiểu 6 ký tự'}), 400
    if 'c_user=' not in cookie:
        return jsonify({'ok': False, 'error': 'Cookie chưa có c_user, vui lòng kiểm tra lại'}), 400

    salt, digest = _hash_password(password)
    now = datetime.utcnow().isoformat(timespec='seconds') + 'Z'
    staff_id = uuid.uuid4().hex[:12]
    _staff_cookies = {
        'active_staff_id': staff_id,
        'staff': [{
            'id': staff_id,
            'name': name,
            'username': username,
            'password_salt': salt,
            'password_hash': digest,
            'cookie': cookie,
            'role': 'admin',
            'enabled': True,
            'created_at': now,
            'updated_at': now,
        }]
    }
    _save_staff_cookies()
    session['staff_id'] = staff_id
    _invalidate_facebook_cache()
    return jsonify({'ok': True, 'staff': _public_current_staff()})


@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    body = request.get_json() or {}
    username = str(body.get('username') or '').strip().lower()
    password = str(body.get('password') or '')
    staff = next((item for item in _staff_accounts()
                  if item.get('enabled', True) and item.get('username') == username), None)
    if not staff or not _verify_password(password, staff.get('password_salt', ''), staff.get('password_hash', '')):
        return jsonify({'ok': False, 'error': 'Sai tài khoản hoặc mật khẩu'}), 401
    session['staff_id'] = staff['id']
    _invalidate_facebook_cache()
    return jsonify({'ok': True, 'staff': _public_current_staff()})


@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    session.pop('staff_id', None)
    _invalidate_facebook_cache()
    return jsonify({'ok': True})


@app.route('/api/posts')
def api_posts():
    global _seen_ids
    limit = request.args.get('limit', 10, type=int)
    group_ids = [g.strip() for g in request.args.get('groups', DEFAULT_GROUP).split(',') if g.strip()]
    is_first = len(_seen_ids) == 0

    try:
        all_posts = []
        for gid in group_ids:
            posts = get_api(gid).get_posts(limit)
            if posts is None:
                return jsonify({'error': 'Cookie hết hạn hoặc không hợp lệ — cập nhật cookie nhân sự đang dùng rồi tải lại'}), 401
            for p in posts:
                p['_group_id'] = gid
            all_posts.extend(posts)

        all_posts.sort(key=lambda x: x.get('created_time', ''), reverse=True)

        new_ids = set()
        new_posts = []
        for post in all_posts:
            pid = post.get('id')
            if pid and pid not in _seen_ids:
                new_ids.add(pid)
                new_posts.append(post)
                if not is_first:
                    threading.Thread(target=_notify_new_post, args=(post,), daemon=True).start()

        if new_ids:
            _seen_ids.update(new_ids)
            _save_seen(new_posts)

        return jsonify(all_posts)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/post', methods=['POST'])
def api_create_post():
    body = request.get_json() or {}
    group_id = body.get('group_id', '').strip()
    message = body.get('message', '').strip()
    page_id = body.get('page_id', '').strip()
    if not group_id or not message:
        return jsonify({'ok': False, 'error': 'Thiếu group_id hoặc message'}), 400
    try:
        page_token = _pages_cache.get(page_id, {}).get('access_token') if page_id else None
        result = get_api(group_id).create_post(message, page_token)
        if result and 'id' in result:
            return jsonify({'ok': True, 'post_id': result['id']})
        err = (result or {}).get('error', {}).get('message', 'Lỗi không xác định')
        return jsonify({'ok': False, 'error': err})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/pages')
def api_pages():
    global _pages_cache
    try:
        pages = get_api(DEFAULT_GROUP).get_pages() or []
        _pages_cache = {p['id']: {'name': p['name'], 'access_token': p['access_token']} for p in pages}
        return jsonify([{'id': p['id'], 'name': p['name']} for p in pages])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/comment', methods=['POST'])
def api_comment():
    body = request.get_json() or {}
    post_id = body.get('post_id', '').strip()
    message = body.get('message', '').strip()
    group_id = body.get('group_id', DEFAULT_GROUP)
    page_id = body.get('page_id', '').strip()
    post_url = body.get('post_url', '').strip()
    if not post_id or not message:
        return jsonify({'ok': False, 'error': 'Thiếu post_id hoặc message'}), 400
    try:
        page_token = _pages_cache.get(page_id, {}).get('access_token') if page_id else None
        result = get_api(group_id).post_comment(post_id, message, page_token)
        if result and 'id' in result:
            log = _record_comment_log(post_id, group_id, post_url, message, page_id, 'success', comment_id=result['id'])
            payload = {'ok': True, 'comment_id': result['id'], 'log_storage': log.get('storage')}
            if log.get('storage_warning'):
                payload['warning'] = f"Đã lưu local, Supabase chưa ghi được: {log['storage_warning']}"
            return jsonify(payload)
        err = (result or {}).get('error', {}).get('message', 'Lỗi không xác định')
        log = _record_comment_log(post_id, group_id, post_url, message, page_id, 'failed', error_message=err)
        payload = {'ok': False, 'error': err, 'log_storage': log.get('storage')}
        if log.get('storage_warning'):
            payload['warning'] = f"Đã lưu local, Supabase chưa ghi được: {log['storage_warning']}"
        return jsonify(payload)
    except Exception as e:
        err = str(e)
        log = _record_comment_log(post_id, group_id, post_url, message, page_id, 'failed', error_message=err)
        payload = {'ok': False, 'error': err, 'log_storage': log.get('storage')}
        if log.get('storage_warning'):
            payload['warning'] = f"Đã lưu local, Supabase chưa ghi được: {log['storage_warning']}"
        return jsonify(payload), 500


@app.route('/api/comment-logs', methods=['GET'])
def comment_logs_get():
    if not _is_admin():
        staff_id = _current_staff_id()
        rows = [item for item in _comment_logs if item.get('staff_id') == staff_id]
    else:
        rows = _comment_logs
    return jsonify(rows[-200:])


@app.route('/api/comment-stats/today', methods=['GET'])
def comment_stats_today():
    staff_id = '' if _is_admin() else _current_staff_id()
    count, warning = _count_today_success_supabase(staff_id)
    storage = 'supabase'
    if count is None:
        count = _count_today_success_local(staff_id)
        storage = 'local'
    payload = {
        'ok': True,
        'success_count': count,
        'storage': storage,
        'scope': 'all' if _is_admin() else 'self',
    }
    if warning and storage == 'local':
        payload['warning'] = warning
    return jsonify(payload)


@app.route('/api/groups/resolve')
def api_resolve_group():
    slug = request.args.get('slug', '').strip()
    if not slug:
        return jsonify({'ok': False, 'error': 'Thiếu slug'}), 400
    try:
        api = get_api(DEFAULT_GROUP)
        data = api.resolve_slug(slug)
        if data and 'id' in data:
            is_member = api.check_membership(data['id'])
            return jsonify({'ok': True, 'id': data['id'], 'name': data.get('name', slug), 'is_member': is_member})
        if data is None and not api.access_token:
            return jsonify({
                'ok': False,
                'error': 'Cookie/token Facebook hết hạn — cập nhật data/cookie.txt rồi restart server',
            }), 401
        err = (data or {}).get('error', {}).get('message', 'Không tìm thấy group')
        return jsonify({'ok': False, 'error': err})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/groups/<gid>/join', methods=['POST'])
def api_join_group(gid):
    try:
        result = get_api(DEFAULT_GROUP).join_group(gid)
        return jsonify(result)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/telegram/chatids', methods=['GET'])
def tg_get():
    return jsonify(_tg_chat_ids)


@app.route('/api/telegram/chatids', methods=['POST'])
def tg_add():
    cid = (request.get_json() or {}).get('chat_id', '').strip()
    if not cid:
        return jsonify({'ok': False, 'error': 'Thiếu chat_id'}), 400
    if cid not in _tg_chat_ids:
        _tg_chat_ids.append(cid)
        _save_tg()
        if USE_SUPABASE:
            try:
                sb.add_chat_id(cid)
            except Exception as e:
                print(f'[supabase] add_chat_id failed: {e}')
    return jsonify({'ok': True, 'chat_ids': _tg_chat_ids})


@app.route('/api/telegram/chatids/<chat_id>', methods=['DELETE'])
def tg_remove(chat_id):
    if chat_id in _tg_chat_ids:
        _tg_chat_ids.remove(chat_id)
        _save_tg()
        if USE_SUPABASE:
            try:
                sb.remove_chat_id(chat_id)
            except Exception as e:
                print(f'[supabase] remove_chat_id failed: {e}')
    return jsonify({'ok': True, 'chat_ids': _tg_chat_ids})


@app.route('/api/groups', methods=['GET'])
def groups_get():
    return jsonify(_groups)


@app.route('/api/groups', methods=['POST'])
def groups_add():
    global _groups
    body = request.get_json() or {}
    gid = body.get('id', '').strip()
    name = body.get('name', '').strip()
    if not gid:
        return jsonify({'ok': False, 'error': 'Thiếu id'}), 400
    if not any(g['id'] == gid for g in _groups):
        _groups.append({'id': gid, 'name': name})
    else:
        for g in _groups:
            if g['id'] == gid and name:
                g['name'] = name
    _save_groups()
    if USE_SUPABASE:
        try:
            sb.upsert_group(gid, name)
        except Exception as e:
            print(f'[supabase] upsert_group failed: {e}')
    return jsonify({'ok': True, 'groups': _groups})


@app.route('/api/groups/<gid>', methods=['DELETE'])
def groups_remove(gid):
    global _groups
    _groups = [g for g in _groups if g['id'] != gid]
    _save_groups()
    if USE_SUPABASE:
        try:
            sb.delete_group(gid)
        except Exception as e:
            print(f'[supabase] delete_group failed: {e}')
    return jsonify({'ok': True, 'groups': _groups})


@app.route('/api/staff-cookies', methods=['GET'])
def staff_cookies_get():
    if _is_admin():
        staff_rows = [_public_staff_cookie(item) for item in _staff_accounts()]
    else:
        staff_rows = [_public_current_staff()] if _current_staff() else []
    return jsonify({
        'active_staff_id': _current_staff_id(),
        'staff': staff_rows,
        'can_manage': _is_admin(),
        'fallback_cookie': bool(load_cookie()),
    })


@app.route('/api/staff-cookies', methods=['POST'])
def staff_cookies_save():
    global _staff_cookies
    if not _is_admin():
        return jsonify({'ok': False, 'error': 'Chỉ admin được thêm nhân sự'}), 403
    body = request.get_json() or {}
    name = str(body.get('name') or '').strip()[:80]
    username = str(body.get('username') or '').strip().lower()[:60]
    password = str(body.get('password') or '')
    cookie = str(body.get('cookie') or '').strip()
    if not name:
        return jsonify({'ok': False, 'error': 'Thiếu tên nhân sự'}), 400
    if not username:
        return jsonify({'ok': False, 'error': 'Thiếu tài khoản đăng nhập'}), 400
    if len(password) < 6:
        return jsonify({'ok': False, 'error': 'Mật khẩu tối thiểu 6 ký tự'}), 400
    if not cookie:
        return jsonify({'ok': False, 'error': 'Thiếu cookie'}), 400
    if 'c_user=' not in cookie:
        return jsonify({'ok': False, 'error': 'Cookie chưa có c_user, vui lòng kiểm tra lại'}), 400

    staff = _staff_cookies.setdefault('staff', [])
    if any(item.get('username') == username for item in staff):
        return jsonify({'ok': False, 'error': 'Tài khoản đăng nhập đã tồn tại'}), 400
    now = datetime.utcnow().isoformat(timespec='seconds') + 'Z'
    saved_id = uuid.uuid4().hex[:12]
    salt, digest = _hash_password(password)
    staff.append({
        'id': saved_id,
        'name': name,
        'username': username,
        'password_salt': salt,
        'password_hash': digest,
        'cookie': cookie,
        'role': 'staff',
        'enabled': True,
        'created_at': now,
        'updated_at': now,
    })
    if not _staff_cookies.get('active_staff_id'):
        _staff_cookies['active_staff_id'] = saved_id
    _save_staff_cookies()
    _invalidate_facebook_cache()
    return jsonify({'ok': True, 'active_staff_id': _current_staff_id(), 'staff': [_public_staff_cookie(item) for item in staff], 'can_manage': True})


@app.route('/api/staff-cookies/<staff_id>/activate', methods=['POST'])
def staff_cookies_activate(staff_id):
    return jsonify({'ok': False, 'error': 'Cookie được gắn theo tài khoản đăng nhập, không cho chọn thủ công'}), 403


@app.route('/api/staff-cookies/<staff_id>', methods=['DELETE'])
def staff_cookies_delete(staff_id):
    if not _is_admin():
        return jsonify({'ok': False, 'error': 'Chỉ admin được xoá nhân sự'}), 403
    if staff_id == _current_staff_id():
        return jsonify({'ok': False, 'error': 'Không thể xoá tài khoản đang đăng nhập'}), 400
    staff = _staff_accounts()
    _staff_cookies['staff'] = [item for item in staff if item.get('id') != staff_id]
    if _staff_cookies.get('active_staff_id') == staff_id:
        _staff_cookies['active_staff_id'] = (_staff_cookies['staff'][0]['id'] if _staff_cookies['staff'] else '')
    try:
        os.remove(_staff_token_file(staff_id))
    except OSError:
        pass
    _save_staff_cookies()
    _invalidate_facebook_cache()
    return jsonify({'ok': True, 'active_staff_id': _current_staff_id(), 'staff': [_public_staff_cookie(item) for item in _staff_cookies.get('staff', [])], 'can_manage': True})


@app.route('/api/settings', methods=['GET'])
def settings_get():
    return jsonify(_settings)


@app.route('/api/settings', methods=['POST'])
def settings_save():
    global _settings
    body = request.get_json() or {}
    _settings.update({k: v for k, v in body.items() if k in ('auto_refresh', 'interval')})
    _save_settings()
    return jsonify({'ok': True, 'settings': _settings})


@app.route('/api/business-profile', methods=['GET'])
def business_profile_get():
    global _business_profile
    try:
        storage = 'local'
        warning = ''
        if not any((_business_profile or {}).values()):
            remote_profile, warning = _load_business_profile_from_supabase()
            if remote_profile:
                _business_profile = {**_default_business_profile(), **remote_profile}
                _save_business_profile()
                storage = 'supabase'
        payload = {'ok': True, 'profile': _business_profile, 'storage': storage}
        if warning:
            payload['warning'] = warning
        return jsonify(payload)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/business-profile', methods=['POST'])
def business_profile_save():
    global _business_profile
    try:
        body = request.get_json() or {}
        _business_profile = _clean_business_profile(body)
        _save_business_profile()

        supabase_ok, supabase_error = _save_business_profile_to_supabase(_business_profile)
        storage = 'supabase' if supabase_ok else 'local'
        payload = {'ok': True, 'profile': _business_profile, 'storage': storage}
        if supabase_error:
            payload['warning'] = f'Đã lưu local, Supabase chưa ghi được: {supabase_error}'
        return jsonify(payload)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/business-profile/generate-text', methods=['POST'])
def business_profile_generate_text():
    global _business_profile
    try:
        body = request.get_json() or {}
        profile = _clean_business_profile(body)
        if not any(profile.values()):
            return jsonify({'ok': False, 'error': 'Nhập ít nhất một thông tin trước khi tạo văn bản'}), 400

        classifier = _get_classifier()
        if not classifier.api_key:
            return jsonify({'ok': False, 'error': 'Chưa cấu hình API key — thêm GEMINI_API_KEY vào .env hoặc key trong UI'}), 400

        generated = classifier.generate_business_text(profile)
        if classifier.last_error and not generated:
            return jsonify({'ok': False, 'error': classifier.last_error}), 502
        if not generated:
            return jsonify({'ok': False, 'error': 'AI chưa tạo được văn bản phù hợp'}), 502

        _business_profile = _clean_business_profile(generated)
        _save_business_profile()

        supabase_ok, supabase_error = _save_business_profile_to_supabase(_business_profile)
        storage = 'supabase' if supabase_ok else 'local'
        payload = {'ok': True, 'profile': _business_profile, 'storage': storage}
        if supabase_error:
            payload['warning'] = f'Đã lưu local, Supabase chưa ghi được: {supabase_error}'
        return jsonify(payload)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/telegram/test/<chat_id>', methods=['POST'])
def tg_test(chat_id):
    try:
        r = _req.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
            json={'chat_id': chat_id, 'text': '✅ Kết nối Telegram thành công!'},
            timeout=10,
        )
        return jsonify({'ok': r.ok})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── AI Routes ──────────────────────────────────────────
@app.route('/api/ai/providers')
def ai_providers():
    return jsonify(PROVIDERS)


@app.route('/api/ai/config', methods=['GET'])
def ai_config_get():
    safe = dict(_ai_config)
    safe_keys = {}
    for k, v in safe.get('keys', {}).items():
        safe_keys[k] = ('***' + v[-4:]) if v and len(v) > 4 else ('***' if v else '')
    safe.pop('keys', None)
    safe['keys_masked'] = safe_keys
    return jsonify(safe)


@app.route('/api/ai/config', methods=['POST'])
def ai_config_save():
    global _ai_config
    body = request.get_json() or {}
    if 'provider' in body:
        _ai_config['provider'] = body['provider']
    if 'model' in body:
        _ai_config['model'] = body['model']
    if 'auto_classify' in body:
        _ai_config['auto_classify'] = bool(body['auto_classify'])
    if 'categories' in body and isinstance(body['categories'], list):
        _ai_config['categories'] = body['categories']
    if 'key' in body:
        provider = body.get('provider', _ai_config.get('provider', 'gemini'))
        if 'keys' not in _ai_config:
            _ai_config['keys'] = {}
        _ai_config['keys'][provider] = body['key']
    _save_ai_config()
    return jsonify({'ok': True})


@app.route('/api/ai/test', methods=['POST'])
def ai_test():
    classifier = _get_classifier()
    if not classifier.api_key:
        return jsonify({'ok': False, 'error': 'Chưa nhập API key'})
    result = classifier.test_connection()
    return jsonify(result)


@app.route('/api/ai/key/<provider>', methods=['DELETE'])
def ai_key_delete(provider):
    global _ai_config
    if 'keys' in _ai_config and provider in _ai_config['keys']:
        _ai_config['keys'][provider] = ''
        _save_ai_config()
    return jsonify({'ok': True})


@app.route('/api/ai/classify', methods=['POST'])
def ai_classify():
    global _classifications
    body = request.get_json() or {}
    posts = body.get('posts', [])
    force = body.get('force', False)
    if not posts:
        return jsonify({'ok': False, 'error': 'Không có bài viết'})
    classifier = _get_classifier()
    if not classifier.api_key:
        return jsonify({'ok': False, 'error': 'Chưa cấu hình API key'})
    to_classify = [p for p in posts if force or p.get('id') not in _classifications]
    if not to_classify:
        return jsonify({'ok': True, 'classifications': {pid: _classifications[pid] for pid in [p['id'] for p in posts] if pid in _classifications}})
    results = classifier.classify_posts(to_classify)
    if classifier.last_error and not results:
        return jsonify({'ok': False, 'error': classifier.last_error}), 502
    _classifications.update(results)
    _save_classifications(results)
    all_results = {p['id']: _classifications.get(p['id'], '') for p in posts}
    return jsonify({'ok': True, 'classifications': all_results})


@app.route('/api/ai/classifications', methods=['GET'])
def ai_classifications_get():
    return jsonify(_classifications)


@app.route('/api/ai/leads', methods=['GET'])
def ai_leads_get():
    return jsonify(_leads)


@app.route('/api/ai/reply-suggestions', methods=['GET'])
def ai_reply_suggestions_get():
    return jsonify(_reply_suggestions)


@app.route('/api/ai/suggest-reply', methods=['POST'])
def ai_suggest_reply():
    global _reply_suggestions
    try:
        body = request.get_json() or {}
        post = body.get('post') or {}
        manual_comment = (body.get('comment') or '').strip()
        if not post:
            return jsonify({'ok': False, 'error': 'Không có bài viết'}), 400

        classifier = _get_classifier()
        if not classifier.api_key:
            return jsonify({'ok': False, 'error': 'Chưa cấu hình API key — thêm GEMINI_API_KEY vào .env hoặc key trong UI'}), 400

        suggestion = classifier.suggest_reply(post, manual_comment, _business_profile)
        if classifier.last_error and not suggestion:
            return jsonify({'ok': False, 'error': classifier.last_error}), 502
        if not suggestion:
            return jsonify({'ok': False, 'error': 'AI chưa tạo được gợi ý phù hợp'}), 502

        pid = suggestion.get('post_id') or post.get('id')
        suggestion['post_id'] = pid
        suggestion['group_id'] = post.get('_group_id', '')
        suggestion['post_url'] = post.get('permalink_url', '')
        _reply_suggestions[pid] = suggestion
        _save_reply_suggestions()

        supabase_ok, supabase_error = _save_reply_suggestion_to_supabase(suggestion)
        storage = 'supabase' if supabase_ok else 'local'
        payload = {'ok': True, 'suggestion': suggestion, 'storage': storage}
        if supabase_error:
            payload['warning'] = f'Đã lưu local, Supabase chưa ghi được: {supabase_error}'
        return jsonify(payload)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/api/ai/extract-leads', methods=['POST'])
def ai_extract_leads():
    global _leads
    body = request.get_json() or {}
    posts = body.get('posts', [])
    force = body.get('force', False)
    if not posts:
        return jsonify({'ok': False, 'error': 'Không có bài viết'})
    classifier = _get_classifier()
    if not classifier.api_key:
        return jsonify({'ok': False, 'error': 'Chưa cấu hình API key'})

    to_extract = [p for p in posts if force or p.get('id') not in _leads]
    if to_extract:
        results = classifier.extract_leads(to_extract)
        if classifier.last_error and not results:
            return jsonify({'ok': False, 'error': classifier.last_error}), 502
        for post in to_extract:
            pid = post.get('id')
            if pid:
                _leads[pid] = results.get(pid, [])
        _save_leads()

    all_results = {p['id']: _leads.get(p['id'], []) for p in posts if p.get('id')}
    payload = {'ok': True, 'leads': all_results}
    if classifier.last_error:
        payload['warning'] = classifier.last_error
    return jsonify(payload)


# ── Supabase ───────────────────────────────────────────
@app.route('/api/supabase/health')
def supabase_health():
    return jsonify({'enabled': USE_SUPABASE, **sb.ping()})


@app.route('/api/saved-posts')
def saved_posts():
    if not USE_SUPABASE:
        return jsonify({'ok': False, 'error': 'Supabase chưa được cấu hình'}), 400
    limit = request.args.get('limit', 100, type=int)
    group_id = (request.args.get('group_id') or '').strip() or None
    try:
        rows = sb.list_saved_posts(limit=limit, group_id=group_id)
        return jsonify({'ok': True, 'count': len(rows), 'posts': rows})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Start ──────────────────────────────────────────────
_load_state()
threading.Thread(target=_poll_telegram, daemon=True).start()

if __name__ == '__main__':
    print(f'[server] supabase={"on" if USE_SUPABASE else "off"} | http://localhost:{PORT}')
    app.run(debug=False, port=PORT)
