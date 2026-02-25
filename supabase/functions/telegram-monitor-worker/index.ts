import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.10";

type SyncState = {
  sync_name: string;
  initialized: boolean;
  last_violation_ts: string;
  last_violation_id: string | null;
  last_break_scan_ts: string;
  last_sent_total: number;
  updated_at: string;
};

type ViolationRow = {
  id: string;
  email: string;
  name: string | null;
  violation_type: string;
  break_type: string | null;
  timestamp: string;
  expected_duration: number | null;
  actual_duration: number | null;
  excess_minutes: number | null;
  details: string | null;
};

type BreakRow = {
  id: string;
  email: string;
  name: string | null;
  break_type: string | null;
  start_time: string;
  end_time: string | null;
  status: string | null;
  session_id: string | null;
};

const SYNC_NAME = "telegram_monitor_worker";
const SYNC_SECRET = Deno.env.get("SYNC_WEBHOOK_SECRET") ?? "";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload, null, 2), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

function envOrThrow(name: string): string {
  const value = Deno.env.get(name);
  if (!value || !value.trim()) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value.trim();
}

function parseBoundedInt(
  raw: string | undefined,
  fallback: number,
  min: number,
  max: number,
): number {
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(min, Math.min(max, Math.floor(parsed)));
}

function parseIsoToMs(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const ms = Date.parse(iso);
  return Number.isNaN(ms) ? null : ms;
}

function normalizeUuidLike(value: string | null | undefined): string {
  return String(value ?? "").toLowerCase().replace(/-/g, "");
}

function isUuidLessOrEqual(left: string | null | undefined, right: string | null | undefined): boolean {
  const a = normalizeUuidLike(left);
  const b = normalizeUuidLike(right);
  if (!a || !b) return false;
  return a <= b;
}

function formatLocalDateTime(iso: string | null | undefined, timeZone: string): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";

  const parts = new Intl.DateTimeFormat("sv-SE", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(date);

  const map = new Map<string, string>();
  for (const part of parts) {
    map.set(part.type, part.value);
  }

  return `${map.get("year")}-${map.get("month")}-${map.get("day")} ${map.get("hour")}:${map.get("minute")}:${map.get("second")}`;
}

function normalizeBreakType(raw: string | null | undefined): string {
  const val = String(raw ?? "").trim();
  if (!val) return "Перерыв";
  const key = val.toLowerCase();
  if (key.includes("обед")) return "Обед";
  if (key.includes("перерыв")) return "Перерыв";
  return val;
}

function getBreakLimitMinutes(
  breakType: string | null | undefined,
  breakLimitMinutes: number,
  lunchLimitMinutes: number,
): number {
  const normalized = normalizeBreakType(breakType).toLowerCase();
  return normalized.includes("обед") ? lunchLimitMinutes : breakLimitMinutes;
}

function buildViolationMessage(v: ViolationRow, timeZone: string): string {
  const violationNameMap: Record<string, string> = {
    OUT_OF_WINDOW: "Вне временного окна",
    OVER_LIMIT: "Превышен лимит времени",
    QUOTA_EXCEEDED: "Превышено количество перерывов",
    break_overtime: "Превышен лимит времени",
    unauthorized_break: "Вне временного окна",
  };

  const t = String(v.violation_type ?? "").trim();
  const localizedType = violationNameMap[t] ?? (t || "Нарушение");
  const when = formatLocalDateTime(v.timestamp, timeZone);
  const who = (v.name || "").trim() || v.email || "Unknown";
  const breakType = normalizeBreakType(v.break_type);
  const details = String(v.details ?? "").trim();
  const excess = v.excess_minutes ?? null;

  let message = "⚠️ <b>НАРУШЕНИЕ ПРАВИЛ ПЕРЕРЫВОВ</b>\n\n";
  message += `Сотрудник: <b>${who}</b>\n`;
  message += `Email: ${v.email}\n`;
  message += `Тип: ${localizedType}\n`;
  if (breakType) {
    message += `Перерыв: ${breakType}\n`;
  }
  if (excess !== null && Number.isFinite(excess)) {
    message += `Превышение: +${Math.max(0, Math.floor(excess))} мин\n`;
  }
  if (when) {
    message += `Время: ${when}\n`;
  }
  if (details) {
    message += `Детали: ${details}\n`;
  }
  return message;
}

function buildBreakWarningMessage(
  b: BreakRow,
  durationMinutes: number,
  limitMinutes: number,
  timeZone: string,
): string {
  const who = (b.name || "").trim() || b.email || "Unknown";
  const breakType = normalizeBreakType(b.break_type);
  const started = formatLocalDateTime(b.start_time, timeZone);
  const excess = Math.max(0, durationMinutes - limitMinutes);

  let message = "⏰ <b>ПРЕВЫШЕНИЕ ЛИМИТА ПЕРЕРЫВА</b>\n\n";
  message += `Сотрудник: <b>${who}</b>\n`;
  message += `Email: ${b.email}\n`;
  message += `Тип: ${breakType}\n`;
  message += `Длительность: ${durationMinutes} мин (лимит ${limitMinutes} мин)\n`;
  message += `Превышение: +${excess} мин\n`;
  if (started) {
    message += `Начало: ${started}\n`;
  }
  return message;
}

async function sendTelegramMessage(
  botToken: string,
  chatId: string,
  text: string,
  silent = false,
): Promise<void> {
  const response = await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      text,
      parse_mode: "HTML",
      disable_notification: silent,
    }),
  });

  const rawText = await response.text();
  let payload: Record<string, unknown> = {};
  try {
    payload = JSON.parse(rawText);
  } catch {
    // ignore parse error, handled below
  }

  const ok = Boolean(payload.ok);
  if (!response.ok || !ok) {
    const description = String(payload.description ?? rawText ?? "");
    throw new Error(`Telegram sendMessage failed (${response.status}): ${description}`);
  }
}

async function isEventSent(
  supabase: ReturnType<typeof createClient>,
  eventKey: string,
): Promise<boolean> {
  const { data, error } = await supabase
    .from("telegram_monitor_sent_events")
    .select("event_key")
    .eq("event_key", eventKey)
    .maybeSingle();

  if (error) {
    throw new Error(`Failed to check sent event ${eventKey}: ${error.message}`);
  }
  return Boolean(data);
}

async function markEventSent(
  supabase: ReturnType<typeof createClient>,
  eventKey: string,
  eventKind: string,
  payload: unknown,
): Promise<void> {
  const { error } = await supabase
    .from("telegram_monitor_sent_events")
    .insert({
      event_key: eventKey,
      event_kind: eventKind,
      sent_at: new Date().toISOString(),
      payload,
    });

  if (error) {
    // Parallel runs can race; duplicate is safe.
    if (String(error.code) === "23505" || error.message.toLowerCase().includes("duplicate")) {
      return;
    }
    throw new Error(`Failed to mark sent event ${eventKey}: ${error.message}`);
  }
}

Deno.serve(async (request: Request) => {
  try {
    if (request.method !== "GET" && request.method !== "POST") {
      return jsonResponse({ ok: false, error: "Method not allowed" }, 405);
    }

    if (SYNC_SECRET) {
      const url = new URL(request.url);
      const incomingSecret = request.headers.get("x-sync-secret") ??
        url.searchParams.get("secret");
      if (incomingSecret !== SYNC_SECRET) {
        return jsonResponse({ ok: false, error: "Unauthorized" }, 401);
      }
    }

    const supabaseUrl = envOrThrow("SUPABASE_URL");
    const supabaseServiceRoleKey = envOrThrow("SUPABASE_SERVICE_ROLE_KEY");
    const botToken = envOrThrow("TELEGRAM_BOT_TOKEN");
    const monitoringChatId = envOrThrow("TELEGRAM_MONITORING_CHAT_ID");

    const timeZone = Deno.env.get("TELEGRAM_TIMEZONE")?.trim() || "Europe/Moscow";
    const batchSize = parseBoundedInt(
      Deno.env.get("TELEGRAM_WORKER_BATCH_SIZE"),
      200,
      1,
      1000,
    );
    const maxLoops = parseBoundedInt(
      Deno.env.get("TELEGRAM_WORKER_MAX_LOOPS"),
      4,
      1,
      20,
    );
    const breakLimitMinutes = parseBoundedInt(
      Deno.env.get("BREAK_LIMIT_MINUTES"),
      15,
      1,
      240,
    );
    const lunchLimitMinutes = parseBoundedInt(
      Deno.env.get("LUNCH_LIMIT_MINUTES"),
      60,
      1,
      240,
    );
    const dedupKeepDays = parseBoundedInt(
      Deno.env.get("TELEGRAM_SENT_KEEP_DAYS"),
      7,
      1,
      90,
    );

    const supabase = createClient(supabaseUrl, supabaseServiceRoleKey, {
      auth: { persistSession: false },
    });

    const { data: stateData, error: stateError } = await supabase
      .from("telegram_monitor_sync_state")
      .select("*")
      .eq("sync_name", SYNC_NAME)
      .maybeSingle();

    if (stateError) {
      throw new Error(`Failed to load sync state: ${stateError.message}`);
    }

    const nowIso = new Date().toISOString();

    // First run: initialize checkpoint at "now", skip old history.
    if (!stateData || !stateData.initialized) {
      const { error: initError } = await supabase
        .from("telegram_monitor_sync_state")
        .upsert({
          sync_name: SYNC_NAME,
          initialized: true,
          last_violation_ts: nowIso,
          last_violation_id: null,
          last_break_scan_ts: nowIso,
          last_sent_total: 0,
          updated_at: nowIso,
        }, { onConflict: "sync_name" });

      if (initError) {
        throw new Error(`Failed to initialize monitor state: ${initError.message}`);
      }

      return jsonResponse({
        ok: true,
        initialized: true,
        skipped_history: true,
        checkpoint: nowIso,
      });
    }

    const state = stateData as SyncState;
    let checkpointTs = state.last_violation_ts;
    let checkpointId = state.last_violation_id;
    let sentViolations = 0;
    let sentBreakWarnings = 0;
    let loops = 0;

    while (loops < maxLoops) {
      loops += 1;

      const { data: rows, error: loadError } = await supabase
        .from("violations")
        .select(
          "id,email,name,violation_type,break_type,timestamp,expected_duration,actual_duration,excess_minutes,details",
        )
        .gte("timestamp", checkpointTs)
        .order("timestamp", { ascending: true })
        .order("id", { ascending: true })
        .limit(batchSize);

      if (loadError) {
        throw new Error(`Failed to load violations: ${loadError.message}`);
      }

      const batch = (rows ?? []) as ViolationRow[];
      if (!batch.length) break;

      const checkpointMs = parseIsoToMs(checkpointTs);
      let processedAny = false;

      for (const row of batch) {
        const rowTsMs = parseIsoToMs(row.timestamp);
        if (rowTsMs === null) continue;
        if (checkpointMs !== null && rowTsMs < checkpointMs) continue;
        if (
          checkpointMs !== null &&
          rowTsMs === checkpointMs &&
          checkpointId &&
          isUuidLessOrEqual(row.id, checkpointId)
        ) {
          continue;
        }

        processedAny = true;
        checkpointTs = row.timestamp;
        checkpointId = row.id;

        const eventKey = `violation:${row.id}`;
        if (await isEventSent(supabase, eventKey)) continue;

        const message = buildViolationMessage(row, timeZone);
        await sendTelegramMessage(botToken, monitoringChatId, message, false);
        await markEventSent(supabase, eventKey, "violation", row);
        sentViolations += 1;
      }

      if (!processedAny || batch.length < batchSize) {
        break;
      }
    }

    // Active breaks over limit: one alert per break instance.
    const { data: breakRows, error: breaksError } = await supabase
      .from("break_log")
      .select("id,email,name,break_type,start_time,end_time,status,session_id")
      .is("end_time", null)
      .order("start_time", { ascending: true })
      .limit(1000);

    if (breaksError) {
      throw new Error(`Failed to load active breaks: ${breaksError.message}`);
    }

    const nowMs = Date.now();
    for (const row of (breakRows ?? []) as BreakRow[]) {
      const startedMs = parseIsoToMs(row.start_time);
      if (startedMs === null) continue;

      const durationMinutes = Math.max(0, Math.floor((nowMs - startedMs) / 60000));
      const limitMinutes = getBreakLimitMinutes(
        row.break_type,
        breakLimitMinutes,
        lunchLimitMinutes,
      );

      if (durationMinutes <= limitMinutes) continue;

      const breakIdentity = row.id || `${row.email}:${row.start_time}`;
      const eventKey = `break_over:${breakIdentity}`;
      if (await isEventSent(supabase, eventKey)) continue;

      const message = buildBreakWarningMessage(row, durationMinutes, limitMinutes, timeZone);
      await sendTelegramMessage(botToken, monitoringChatId, message, false);
      await markEventSent(supabase, eventKey, "break_over_limit", {
        ...row,
        duration_minutes: durationMinutes,
        limit_minutes: limitMinutes,
      });
      sentBreakWarnings += 1;
    }

    const totalNewSent = sentViolations + sentBreakWarnings;
    const prevSentTotal = Number(state.last_sent_total ?? 0);
    const { error: saveStateError } = await supabase
      .from("telegram_monitor_sync_state")
      .upsert({
        sync_name: SYNC_NAME,
        initialized: true,
        last_violation_ts: checkpointTs,
        last_violation_id: checkpointId,
        last_break_scan_ts: new Date().toISOString(),
        last_sent_total: prevSentTotal + totalNewSent,
        updated_at: new Date().toISOString(),
      }, { onConflict: "sync_name" });

    if (saveStateError) {
      throw new Error(`Failed to save sync state: ${saveStateError.message}`);
    }

    // Periodic cleanup to keep dedup table compact.
    const { error: cleanupError } = await supabase.rpc(
      "cleanup_telegram_monitor_sent_events",
      { p_keep_days: dedupKeepDays },
    );
    if (cleanupError) {
      // Non-fatal: worker can continue even if cleanup is unavailable.
      console.warn("cleanup_telegram_monitor_sent_events failed:", cleanupError.message);
    }

    return jsonResponse({
      ok: true,
      sent: {
        violations: sentViolations,
        break_warnings: sentBreakWarnings,
        total: totalNewSent,
      },
      loops,
      batch_size: batchSize,
      checkpoint: {
        last_violation_ts: checkpointTs,
        last_violation_id: checkpointId,
      },
    });
  } catch (error) {
    return jsonResponse(
      {
        ok: false,
        error: String(error),
      },
      500,
    );
  }
});
