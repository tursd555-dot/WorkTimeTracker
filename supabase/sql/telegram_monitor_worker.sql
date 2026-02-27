-- Cloud Telegram monitor worker state for Supabase Edge Function.
-- Safe to run multiple times.

create table if not exists public.telegram_monitor_sync_state (
    sync_name text primary key,
    initialized boolean not null default false,
    last_violation_ts timestamptz not null default 'epoch'::timestamptz,
    last_violation_id uuid,
    last_break_scan_ts timestamptz not null default 'epoch'::timestamptz,
    last_sent_total integer not null default 0,
    updated_at timestamptz not null default now()
);

create table if not exists public.telegram_monitor_sent_events (
    event_key text primary key,
    event_kind text not null,
    sent_at timestamptz not null default now(),
    payload jsonb not null default '{}'::jsonb
);

create index if not exists idx_telegram_monitor_sent_events_sent_at
    on public.telegram_monitor_sent_events (sent_at desc);

create or replace function public.cleanup_telegram_monitor_sent_events(p_keep_days integer default 7)
returns integer
language plpgsql
as $$
declare
    v_deleted integer := 0;
begin
    if p_keep_days < 1 then
        p_keep_days := 1;
    end if;

    delete from public.telegram_monitor_sent_events
    where sent_at < now() - make_interval(days => p_keep_days);

    get diagnostics v_deleted = row_count;
    return v_deleted;
end;
$$;
