# Cloud Telegram monitor in Supabase (24/7 worker)

This setup moves notification logic from local `WorkTimeTracker_Bot.exe` to Supabase:

- worker runs as Edge Function;
- trigger via schedule (every minute);
- dedup/state stored in database;
- no always-on local PC required.

---

## What is added in repo

1. SQL state/dedup:

- `supabase/sql/telegram_monitor_worker.sql`

Creates:

- `telegram_monitor_sync_state`
- `telegram_monitor_sent_events`
- cleanup function `cleanup_telegram_monitor_sent_events(...)`

2. Edge Function worker:

- `supabase/functions/telegram-monitor-worker/index.ts`

Reads:

- new rows from `violations`;
- active over-limit breaks from `break_log`.

Sends messages to Telegram monitoring chat.

---

## 1) Apply SQL in Supabase

Run file content in SQL Editor:

- `supabase/sql/telegram_monitor_worker.sql`

---

## 2) Deploy Edge Function

```bash
supabase functions deploy telegram-monitor-worker --no-verify-jwt
```

---

## 3) Configure secrets in Supabase

Required:

- `SYNC_WEBHOOK_SECRET=<same long random string>`
- `TELEGRAM_BOT_TOKEN=<token from @BotFather>`
- `TELEGRAM_MONITORING_CHAT_ID=<group/user chat id>`

Already used by function runtime:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

Optional tuning:

- `TELEGRAM_TIMEZONE=Europe/Moscow`
- `TELEGRAM_WORKER_BATCH_SIZE=200`
- `TELEGRAM_WORKER_MAX_LOOPS=4`
- `BREAK_LIMIT_MINUTES=15`
- `LUNCH_LIMIT_MINUTES=60`
- `TELEGRAM_SENT_KEEP_DAYS=7`
- `TELEGRAM_BREAK_MAX_AGE_HOURS=12`  (scan only recent active breaks to avoid stale records)
- `TELEGRAM_BREAK_REPEAT_MINUTES=5` (repeat over-limit warning for active break every N minutes)

---

## 4) Test worker manually

```bash
curl -X POST "https://<project-ref>.supabase.co/functions/v1/telegram-monitor-worker" \
  -H "Content-Type: application/json" \
  -H "x-sync-secret: <SYNC_WEBHOOK_SECRET>" \
  -d "{}"
```

Expected response includes:

- `"ok": true`
- `sent.violations`
- `sent.break_warnings`

First run behavior:

- initializes checkpoint at current time;
- skips old history;
- then works incrementally.

---

## 5) Schedule it every minute

In Supabase Dashboard → Edge Functions → Schedules:

- Method: `POST`
- Path: `/functions/v1/telegram-monitor-worker`
- Cron: `* * * * *`
- Header:
  - `x-sync-secret: <SYNC_WEBHOOK_SECRET>`
- Body: `{}`

---

## 6) Keepalive

Keepalive endpoint/workflow remains useful:

- `POST /functions/v1/healthz`
- workflow: `.github/workflows/supabase-keepalive.yml`

This helps avoid cold/sleep periods (especially with external periodic pings).
