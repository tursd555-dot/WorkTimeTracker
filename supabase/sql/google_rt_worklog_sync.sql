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
drop function if exists public.get_worklog_events_for_google_sync(timestamptz, uuid, integer);

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
    comment text,
    details text,
    status_end_ts timestamptz,
    status_duration_sec integer,
    shift_start_ts timestamptz,
    shift_end_ts timestamptz,
    shift_duration_sec integer,
    closes_event_id uuid,
    closes_event_end_ts timestamptz,
    closes_event_duration_sec integer
)
language sql
stable
as $$
    with base as (
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
        where upper(coalesce(wl.action_type, '')) in ('LOGIN', 'LOGOUT', 'STATUS_CHANGE')
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
    ),
    batch as (
        -- Глобальная дедупликация ретраев: оставляем только самую раннюю запись
        -- с одинаковым email/session/action/status/details/timestamp.
        select
            b.id,
            b.created_at,
            b.timestamp,
            b.email,
            b.name,
            b.session_id,
            b.action_type,
            b.status,
            b.details
        from base b
        where not exists (
            select 1
            from public.work_log w0
            where lower(coalesce(w0.email, '')) = lower(coalesce(b.email, ''))
              and coalesce(w0.session_id, '') = coalesce(b.session_id, '')
              and upper(coalesce(w0.action_type, '')) = upper(coalesce(b.action_type, ''))
              and coalesce(w0.status, '') = coalesce(b.status, '')
              and coalesce(w0.details, '') = coalesce(b.details, '')
              and w0.timestamp = b.timestamp
              and (
                  w0.created_at < b.created_at
                  or (w0.created_at = b.created_at and w0.id::text < b.id::text)
              )
        )
        order by b.created_at asc, b.id asc
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
            upper(coalesce(b.action_type, ''))::text as action_type,
            coalesce(b.status, '')::text as status,
            coalesce(b.details, '')::text as comment,
            coalesce(b.details, '')::text as details,
            nxt.next_ts as status_end_ts,
            sh.shift_start_ts as shift_start_ts,
            sh.shift_end_ts as shift_end_ts,
            case
                when sh.shift_start_ts is not null and sh.shift_end_ts is not null and sh.shift_end_ts >= sh.shift_start_ts
                    then greatest(0, extract(epoch from (sh.shift_end_ts - sh.shift_start_ts))::integer)
                else null
            end as shift_duration_sec,
            prv.prev_id as closes_event_id,
            b.timestamp as closes_event_end_ts,
            case
                when prv.prev_ts is not null
                    then greatest(0, extract(epoch from (b.timestamp - prv.prev_ts))::integer)
                else null
            end as closes_event_duration_sec
        from batch b
        left join public.users u
            on lower(u.email) = lower(b.email)
        left join lateral (
            select wl2.timestamp as next_ts
            from public.work_log wl2
            where lower(wl2.email) = lower(b.email)
              and upper(coalesce(wl2.action_type, '')) in ('LOGIN', 'LOGOUT', 'STATUS_CHANGE')
              and (
                  coalesce(b.session_id, '') = ''
                  or coalesce(wl2.session_id, '') = coalesce(b.session_id, '')
                  or coalesce(wl2.session_id, '') = ''
              )
              and wl2.timestamp > b.timestamp
            order by
                case
                    when coalesce(wl2.session_id, '') = coalesce(b.session_id, '') then 0
                    when coalesce(wl2.session_id, '') = '' then 1
                    else 2
                end,
                wl2.timestamp asc,
                wl2.id asc
            limit 1
        ) nxt
            on upper(coalesce(b.action_type, '')) in ('LOGIN', 'STATUS_CHANGE')
        left join lateral (
            select
                min(case when upper(coalesce(wl_s.action_type, '')) = 'LOGIN' then wl_s.timestamp end) as shift_start_ts,
                min(case when upper(coalesce(wl_s.action_type, '')) = 'LOGOUT' then wl_s.timestamp end) as shift_end_ts
            from public.work_log wl_s
            where lower(wl_s.email) = lower(b.email)
              and upper(coalesce(wl_s.action_type, '')) in ('LOGIN', 'LOGOUT')
              and (
                  (coalesce(b.session_id, '') <> '' and coalesce(wl_s.session_id, '') = coalesce(b.session_id, ''))
                  or (coalesce(b.session_id, '') = '' and coalesce(wl_s.session_id, '') = '')
              )
        ) sh
            on true
        left join lateral (
            select
                wl_prev.id as prev_id,
                wl_prev.timestamp as prev_ts
            from public.work_log wl_prev
            where lower(wl_prev.email) = lower(b.email)
              and upper(coalesce(wl_prev.action_type, '')) in ('LOGIN', 'STATUS_CHANGE')
              and (
                  coalesce(b.session_id, '') = ''
                  or coalesce(wl_prev.session_id, '') = coalesce(b.session_id, '')
                  or coalesce(wl_prev.session_id, '') = ''
              )
              and wl_prev.timestamp < b.timestamp
            order by
                case
                    when coalesce(wl_prev.session_id, '') = coalesce(b.session_id, '') then 0
                    when coalesce(wl_prev.session_id, '') = '' then 1
                    else 2
                end,
                wl_prev.timestamp desc,
                wl_prev.id desc
            limit 1
        ) prv
            on upper(coalesce(b.action_type, '')) in ('STATUS_CHANGE', 'LOGOUT')
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
        e.comment,
        e.details,
        e.status_end_ts,
        case
            when e.action_type in ('LOGIN', 'STATUS_CHANGE') and e.status_end_ts is not null
                then greatest(0, extract(epoch from (e.status_end_ts - e.event_ts))::integer)
            else null
        end as status_duration_sec,
        e.shift_start_ts,
        e.shift_end_ts,
        e.shift_duration_sec,
        e.closes_event_id,
        e.closes_event_end_ts,
        e.closes_event_duration_sec
    from enriched e
    order by e.created_at asc, e.event_id asc;
$$;

comment on function public.get_worklog_events_for_google_sync is
'Incremental feed for realtime Google Sheets export. Includes group name and computed status duration.';
