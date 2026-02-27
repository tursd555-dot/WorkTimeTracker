# Supabase Keepalive setup (healthz + external pings)

This setup keeps the Supabase project active by calling a lightweight Edge Function from outside (GitHub Actions / UptimeRobot / cron-job.org).

> Important: internal jobs (`pg_cron`) do not wake a sleeping project.  
> Keepalive must come from an external scheduler.

---

## 1) Deploy the `healthz` function

From project root:

```bash
supabase functions deploy healthz --no-verify-jwt
```

Function path in repo:

- `supabase/functions/healthz/index.ts`

---

## 2) Configure secret in Supabase

Set secret in Supabase project:

- `SYNC_WEBHOOK_SECRET=<long random string>`

`healthz` validates:

- header `x-sync-secret: <SYNC_WEBHOOK_SECRET>`

or query parameter:

- `?secret=<SYNC_WEBHOOK_SECRET>`

---

## 3) Test endpoint manually

```bash
curl -X POST "https://<project-ref>.supabase.co/functions/v1/healthz" \
  -H "Content-Type: application/json" \
  -H "x-sync-secret: <SYNC_WEBHOOK_SECRET>" \
  -d "{}"
```

Expected response:

```json
{
  "ok": true,
  "service": "healthz",
  "timestamp": "2026-02-25T12:34:56.789Z"
}
```

---

## 4) GitHub Actions keepalive (already added)

Workflow file:

- `.github/workflows/supabase-keepalive.yml`

It runs daily (`03:17 UTC`) and can also be started manually (`workflow_dispatch`).

Add repository secrets:

- `SUPABASE_PROJECT_URL` → `https://<project-ref>.supabase.co`
- `SYNC_WEBHOOK_SECRET` → same value as in Supabase secret

---

## 5) Alternative schedulers

If you prefer a no-code scheduler:

### UptimeRobot

- Method: `POST`
- URL: `https://<project-ref>.supabase.co/functions/v1/healthz`
- Interval: every 6h or daily
- Custom header: `x-sync-secret: <SYNC_WEBHOOK_SECRET>`
- Body: `{}`

### cron-job.org

- Method: `POST`
- URL: `https://<project-ref>.supabase.co/functions/v1/healthz`
- Schedule: daily (or every 6h)
- Header: `x-sync-secret: <SYNC_WEBHOOK_SECRET>`
- Body: `{}`

---

## Notes

- Daily ping is usually enough for baseline activity checks.
- For stronger anti-sleep behavior, use every 1-6 hours.
- Keep `SYNC_WEBHOOK_SECRET` private; do not expose it in public URLs.
