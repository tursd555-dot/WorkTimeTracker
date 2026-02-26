-- Fix historical break_log time anomalies caused by timezone drift / mixed naive timestamps.
-- Safe to run multiple times.

BEGIN;

-- 1) Normalize obvious +3h shifted start_time rows using created_at as source of truth.
-- We only touch rows where start_time is ~3 hours ahead of created_at (±5 minutes).
UPDATE break_log
SET
  start_time = created_at,
  date = (created_at AT TIME ZONE 'UTC')::date,
  updated_at = NOW()
WHERE
  created_at IS NOT NULL
  AND ABS(EXTRACT(EPOCH FROM (start_time - created_at)) - 10800) <= 300;

-- 2) If end_time is before start_time, treat end_time as invalid and re-open row for manual reconciliation.
UPDATE break_log
SET
  end_time = NULL,
  duration_minutes = NULL,
  status = 'Active',
  updated_at = NOW()
WHERE
  end_time IS NOT NULL
  AND end_time < start_time;

-- 3) Recalculate duration for completed rows with sane timestamps.
UPDATE break_log
SET
  duration_minutes = GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (end_time - start_time)) / 60)::int),
  updated_at = NOW()
WHERE
  end_time IS NOT NULL
  AND end_time >= start_time;

COMMIT;
