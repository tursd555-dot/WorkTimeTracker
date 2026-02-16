-- =============================================================================
-- Realtime export: Supabase work_log -> Google Sheets (single sheet)
-- =============================================================================
-- Run this script in Supabase SQL Editor before deploying Edge Function.
--
-- What it creates:
-- 1) google_reports_sync_state - checkpoint table for incremental export
-- 2) get_worklog_events_for_google_sync(...) - RPC for batch event fetch
-- 3) Helpful indexes for fast incremental reads
-- =============================================================================

-- Checkpoint/state table for one or more sync workers.
create table if not exists public.google_reports_sync_state (
    sync_name text primary key,
    initialized boolean not null default false,
    last_created_at timestamptz not null default 'epoch'::timestamptz,
    last_event_id uuid,
    last_exported_rows integer not null default 0,
    updated_at timestamptz not null default now()
);

comment on table public.google_reports_sync_state is
'Stores incremental sync checkpoint for Google Sheets realtime export.';

-- Fast incremental scans by created_at/id.
create index if not exists idx_work_log_created_at_id
    on public.work_log (created_at, id);

-- Fast lookup of "next status event" by operator/session.
create index if not exists idx_work_log_email_session_ts
    on public.work_log (lower(email), session_id, "timestamp", id);

-- Incremental feed for Edge Function.
-- Returns only LOGIN / LOGOUT / STATUS_CHANGE events.
create or replace function public.get_worklog_events_for_google_sync(
    p_after_created_at timestamptz,
    p_after_event_id uuid default null,
    p_limit integer default 500
)
returns table (
    event_id uuid,
    created_at timestamptz,
    event_ts timestamptz,
    email text,
    name text,
    group_name text,
    session_id text,
    action_type text,
    status text,
    details text,
    status_end_ts timestamptz,
    status_duration_sec integer
)
language sql
stable
as $$
    with batch as (
        select
            wl.id,
            wl.created_at,
            wl.timestamp,
            wl.email,
            wl.name,
            wl.session_id,
            wl.action_type,
            wl.status,
            wl.details
        from public.work_log wl
        where wl.action_type in ('LOGIN', 'LOGOUT', 'STATUS_CHANGE')
          and (
              wl.created_at > coalesce(p_after_created_at, 'epoch'::timestamptz)
              or (
                  wl.created_at = coalesce(p_after_created_at, 'epoch'::timestamptz)
                  and (
                      p_after_event_id is null
                      or wl.id::text > p_after_event_id::text
                  )
              )
          )
        order by wl.created_at asc, wl.id asc
        limit greatest(1, least(coalesce(p_limit, 500), 5000))
    ),
    enriched as (
        select
            b.id as event_id,
            b.created_at,
            b.timestamp as event_ts,
            lower(b.email)::text as email,
            coalesce(nullif(b.name, ''), u.name, '')::text as name,
            coalesce(nullif(u.group_name, ''), 'Без группы')::text as group_name,
            coalesce(b.session_id, '')::text as session_id,
            b.action_type::text as action_type,
            coalesce(b.status, '')::text as status,
            coalesce(b.details, '')::text as details,
            nxt.next_ts as status_end_ts
        from batch b
        left join public.users u
            on lower(u.email) = lower(b.email)
        left join lateral (
            select wl2.timestamp as next_ts
            from public.work_log wl2
            where lower(wl2.email) = lower(b.email)
              and coalesce(wl2.session_id, '') = coalesce(b.session_id, '')
              and (
                  wl2.timestamp > b.timestamp
                  or (wl2.timestamp = b.timestamp and wl2.id::text > b.id::text)
              )
            order by wl2.timestamp asc, wl2.id asc
            limit 1
        ) nxt
            on b.action_type in ('LOGIN', 'STATUS_CHANGE')
    )
    select
        e.event_id,
        e.created_at,
        e.event_ts,
        e.email,
        e.name,
        e.group_name,
        e.session_id,
        e.action_type,
        e.status,
        e.details,
        e.status_end_ts,
        case
            when e.action_type in ('LOGIN', 'STATUS_CHANGE') and e.status_end_ts is not null
                then greatest(0, extract(epoch from (e.status_end_ts - e.event_ts))::integer)
            else null
        end as status_duration_sec
    from enriched e
    order by e.created_at asc, e.event_id asc;
$$;

comment on function public.get_worklog_events_for_google_sync is
'Incremental feed for realtime Google Sheets export. Includes group name and computed status duration.';
