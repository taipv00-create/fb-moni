-- ============================================================
-- Schema cho fb-moni  (chạy 1 lần trong Supabase → SQL Editor)
-- ============================================================

create table if not exists public.groups (
    id          text primary key,
    name        text not null default '',
    created_at  timestamptz not null default now()
);

create table if not exists public.telegram_chat_ids (
    chat_id     text primary key,
    created_at  timestamptz not null default now()
);

create table if not exists public.app_kv (
    key         text primary key,
    value       jsonb not null,
    updated_at  timestamptz not null default now()
);

create table if not exists public.seen_posts (
    post_id       text primary key,
    permalink_url text,
    group_id      text,
    author_name   text,
    message       text,
    created_time  timestamptz,
    seen_at       timestamptz not null default now()
);

-- Khi đã có bảng seen_posts từ trước, chạy các ALTER bên dưới
-- để bổ sung cột metadata (idempotent):
alter table public.seen_posts add column if not exists permalink_url text;
alter table public.seen_posts add column if not exists group_id      text;
alter table public.seen_posts add column if not exists author_name   text;
alter table public.seen_posts add column if not exists message       text;
alter table public.seen_posts add column if not exists created_time  timestamptz;

create index if not exists seen_posts_created_time_idx
    on public.seen_posts (created_time desc);
create index if not exists seen_posts_group_id_idx
    on public.seen_posts (group_id);

create table if not exists public.classifications (
    post_id     text primary key,
    category    text not null,
    updated_at  timestamptz not null default now()
);

-- ── RLS: app dùng service_role nên có thể disable cho gọn ──
alter table public.groups            disable row level security;
alter table public.telegram_chat_ids disable row level security;
alter table public.app_kv            disable row level security;
alter table public.seen_posts        disable row level security;
alter table public.classifications   disable row level security;
