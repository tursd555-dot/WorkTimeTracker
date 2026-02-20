import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.10";
import { SignJWT, importPKCS8 } from "npm:jose@5.9.6";

type SyncState = {
  sync_name: string;
  initialized: boolean;
  last_created_at: string;
  last_event_id: string | null;
  last_exported_rows: number;
  updated_at: string;
};

type ExportEvent = {
  event_id: string;
  created_at: string;
  event_ts: string;
  email: string;
  name: string;
  group_name: string;
  session_id: string;
  action_type: string;
  status: string;
  comment: string;
  details: string;
  status_end_ts: string | null;
  status_duration_sec: number | null;
  shift_start_ts: string | null;
  shift_end_ts: string | null;
  shift_duration_sec: number | null;
  closes_event_id: string | null;
  closes_event_end_ts: string | null;
  closes_event_duration_sec: number | null;
};

const SYNC_NAME = "google_rt_worklog_sync";
const SYNC_SECRET = Deno.env.get("SYNC_WEBHOOK_SECRET") ?? "";

const SHEET_HEADER = [
  "EventId",
  "Email",
  "Name",
  "Group",
  "SessionID",
  "ShiftStartLocal",
  "ShiftEndLocal",
  "ShiftDuration",
  "ActionType",
  "Status",
  "StatusStartLocal",
  "StatusEndLocal",
  "StatusDuration",
  "Comment",
];

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

function normalizePrivateKey(raw: string): string {
  return raw.includes("\\n") ? raw.replace(/\\n/g, "\n") : raw;
}

function safeJsonParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

async function getGoogleAccessToken(
  clientEmail: string,
  privateKeyPem: string,
): Promise<string> {
  const key = await importPKCS8(privateKeyPem, "RS256");
  const now = Math.floor(Date.now() / 1000);

  const assertion = await new SignJWT({
    scope: "https://www.googleapis.com/auth/spreadsheets",
  })
    .setProtectedHeader({ alg: "RS256", typ: "JWT" })
    .setIssuer(clientEmail)
    .setAudience("https://oauth2.googleapis.com/token")
    .setIssuedAt(now)
    .setExpirationTime(now + 3600)
    .sign(key);

  const tokenResponse = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer",
      assertion,
    }),
  });

  const tokenText = await tokenResponse.text();
  const tokenData = safeJsonParse(tokenText) as
    | { access_token?: string; error_description?: string; error?: string }
    | null;

  if (!tokenResponse.ok || !tokenData?.access_token) {
    throw new Error(
      `Failed to get Google access token (${tokenResponse.status}): ${
        tokenData?.error_description ?? tokenData?.error ?? tokenText
      }`,
    );
  }

  return tokenData.access_token;
}

async function googleJsonRequest(
  accessToken: string,
  url: string,
  init: RequestInit = {},
): Promise<unknown> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${accessToken}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(url, { ...init, headers });
  const text = await response.text();
  const payload = safeJsonParse(text);

  if (!response.ok) {
    const message = (payload as { error?: { message?: string } } | null)?.error
      ?.message ?? text;
    throw new Error(`Google API ${response.status}: ${message}`);
  }

  return payload;
}

function rangesEqual(left: string[], right: string[]): boolean {
  if (left.length !== right.length) return false;
  for (let i = 0; i < left.length; i += 1) {
    if ((left[i] ?? "").trim() !== (right[i] ?? "").trim()) return false;
  }
  return true;
}

async function ensureSheetExists(
  accessToken: string,
  spreadsheetId: string,
  sheetName: string,
): Promise<void> {
  const url = `https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}:batchUpdate`;
  const body = {
    requests: [
      {
        addSheet: {
          properties: { title: sheetName },
        },
      },
    ],
  };

  try {
    await googleJsonRequest(accessToken, url, {
      method: "POST",
      body: JSON.stringify(body),
    });
  } catch (error) {
    const message = String(error);
    // If the sheet already exists, we can continue.
    if (!message.includes("already exists")) {
      throw error;
    }
  }
}

async function getSheetHeaderRow(
  accessToken: string,
  spreadsheetId: string,
  sheetName: string,
): Promise<string[] | null> {
  const range = encodeURIComponent(`'${sheetName}'!1:1`);
  const url =
    `https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}/values/${range}?majorDimension=ROWS`;

  try {
    const payload = await googleJsonRequest(accessToken, url) as {
      values?: string[][];
    };
    const firstRow = payload.values?.[0];
    if (!firstRow) return [];
    return firstRow.map((v) => String(v ?? ""));
  } catch (error) {
    const message = String(error);
    if (
      message.includes("Unable to parse range") ||
      message.includes("Requested entity was not found")
    ) {
      return null;
    }
    throw error;
  }
}

async function updateHeaderRow(
  accessToken: string,
  spreadsheetId: string,
  sheetName: string,
  header: string[],
): Promise<void> {
  const range = encodeURIComponent(`'${sheetName}'!A1:${String.fromCharCode(64 + header.length)}1`);
  const url =
    `https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}/values/${range}?valueInputOption=RAW`;
  await googleJsonRequest(accessToken, url, {
    method: "PUT",
    body: JSON.stringify({ values: [header] }),
  });
}

async function ensureSheetAndHeader(
  accessToken: string,
  spreadsheetId: string,
  sheetName: string,
  header: string[],
): Promise<void> {
  let existingHeader = await getSheetHeaderRow(accessToken, spreadsheetId, sheetName);
  if (existingHeader === null) {
    await ensureSheetExists(accessToken, spreadsheetId, sheetName);
    existingHeader = await getSheetHeaderRow(accessToken, spreadsheetId, sheetName);
  }

  if (!existingHeader || !rangesEqual(existingHeader, header)) {
    await updateHeaderRow(accessToken, spreadsheetId, sheetName, header);
  }
}

async function appendRows(
  accessToken: string,
  spreadsheetId: string,
  sheetName: string,
  rows: string[][],
): Promise<void> {
  if (!rows.length) return;
  const range = encodeURIComponent(`'${sheetName}'!A1`);
  const url =
    `https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}/values/${range}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS`;
  await googleJsonRequest(accessToken, url, {
    method: "POST",
    body: JSON.stringify({ values: rows }),
  });
}

async function getEventRowMap(
  accessToken: string,
  spreadsheetId: string,
  sheetName: string,
): Promise<Map<string, number>> {
  const range = encodeURIComponent(`'${sheetName}'!A2:A`);
  const url =
    `https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}/values/${range}?majorDimension=ROWS`;

  const payload = await googleJsonRequest(accessToken, url) as {
    values?: string[][];
  };

  const rows = payload.values ?? [];
  const map = new Map<string, number>();
  for (let i = 0; i < rows.length; i += 1) {
    const eventId = String(rows[i]?.[0] ?? "").trim();
    if (eventId) {
      map.set(eventId, i + 2); // sheet row index (header is row 1)
    }
  }
  return map;
}

async function getSessionRowMap(
  accessToken: string,
  spreadsheetId: string,
  sheetName: string,
): Promise<Map<string, number[]>> {
  const range = encodeURIComponent(`'${sheetName}'!E2:E`);
  const url =
    `https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}/values/${range}?majorDimension=ROWS`;

  const payload = await googleJsonRequest(accessToken, url) as {
    values?: string[][];
  };

  const rows = payload.values ?? [];
  const map = new Map<string, number[]>();
  for (let i = 0; i < rows.length; i += 1) {
    const sessionId = String(rows[i]?.[0] ?? "").trim();
    if (!sessionId) continue;
    const rowNumber = i + 2;
    const existing = map.get(sessionId) ?? [];
    existing.push(rowNumber);
    map.set(sessionId, existing);
  }
  return map;
}

async function batchUpdateValues(
  accessToken: string,
  spreadsheetId: string,
  updates: Array<{ range: string; values: string[][] }>,
): Promise<void> {
  if (!updates.length) return;

  const url =
    `https://sheets.googleapis.com/v4/spreadsheets/${spreadsheetId}/values:batchUpdate`;
  await googleJsonRequest(accessToken, url, {
    method: "POST",
    body: JSON.stringify({
      valueInputOption: "RAW",
      data: updates,
    }),
  });
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

function normalizeActionType(actionType: string | null | undefined): string {
  return String(actionType ?? "").trim().toUpperCase();
}

function normalizeStatus(status: string | null | undefined): string {
  const raw = String(status ?? "").trim();
  if (!raw) return "";

  const key = raw.toLowerCase();
  const canonical: Record<string, string> = {
    "в работе": "В работе",
    "чат": "Чат",
    "аудио": "Аудио",
    "запись": "Запись",
    "анкеты": "Анкеты",
    "перерыв": "Перерыв",
    "обед": "Обед",
    "цито": "ЦИТО",
    "обучение": "Обучение",
  };

  return canonical[key] ?? raw;
}

function formatDuration(totalSec: number | null | undefined): string {
  if (totalSec === null || totalSec === undefined || !Number.isFinite(totalSec)) {
    return "";
  }
  const sec = Math.max(0, Math.floor(totalSec));
  const hh = Math.floor(sec / 3600);
  const mm = Math.floor((sec % 3600) / 60);
  const ss = sec % 60;
  return `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
}

function eventToSheetRow(event: ExportEvent, timeZone: string): string[] {
  const actionType = normalizeActionType(event.action_type);
  const normalizedStatus = normalizeStatus(event.status);
  const statusStartLocal = formatLocalDateTime(event.event_ts, timeZone);
  const durationSec = event.status_duration_sec ?? null;
  let statusEndLocal = formatLocalDateTime(event.status_end_ts, timeZone);
  let statusDuration = formatDuration(durationSec);
  const shiftStartLocal = formatLocalDateTime(event.shift_start_ts, timeZone);
  const shiftEndLocal = formatLocalDateTime(event.shift_end_ts, timeZone);

  // Для явной фиксации логаута в отчете показываем момент логаута
  // как начало/конец статуса с нулевой длительностью.
  if (actionType === "LOGOUT") {
    statusEndLocal = statusStartLocal;
    statusDuration = "00:00:00";
  }

  return [
    event.event_id ?? "",
    event.email ?? "",
    event.name ?? "",
    event.group_name ?? "Без группы",
    event.session_id ?? "",
    shiftStartLocal,
    shiftEndLocal,
    formatDuration(event.shift_duration_sec),
    actionType,
    normalizedStatus,
    statusStartLocal,
    statusEndLocal,
    statusDuration,
    event.comment ?? "",
  ];
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
    const spreadsheetId = envOrThrow("GOOGLE_SPREADSHEET_ID");
    const googleClientEmail = envOrThrow("GOOGLE_SERVICE_ACCOUNT_EMAIL");
    const googlePrivateKey = normalizePrivateKey(
      envOrThrow("GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY"),
    );

    const sheetName = Deno.env.get("GOOGLE_REPORTS_SHEET_NAME")?.trim() ||
      "RT_Events";
    const timeZone = Deno.env.get("REPORTS_TIMEZONE")?.trim() || "Europe/Moscow";
    const batchSize = parseBoundedInt(
      Deno.env.get("REPORTS_BATCH_SIZE"),
      500,
      1,
      5000,
    );
    const maxLoops = parseBoundedInt(
      Deno.env.get("REPORTS_MAX_LOOPS"),
      6,
      1,
      20,
    );

    const supabase = createClient(supabaseUrl, supabaseServiceRoleKey, {
      auth: { persistSession: false },
    });

    const googleAccessToken = await getGoogleAccessToken(
      googleClientEmail,
      googlePrivateKey,
    );
    await ensureSheetAndHeader(
      googleAccessToken,
      spreadsheetId,
      sheetName,
      SHEET_HEADER,
    );

    const { data: state, error: stateError } = await supabase
      .from("google_reports_sync_state")
      .select("*")
      .eq("sync_name", SYNC_NAME)
      .maybeSingle();

    if (stateError) {
      throw new Error(`Failed to load sync state: ${stateError.message}`);
    }

    const nowIso = new Date().toISOString();

    // First run: initialize checkpoint at "now" (skip history).
    if (!state || !state.initialized) {
      const { error: initError } = await supabase
        .from("google_reports_sync_state")
        .upsert({
          sync_name: SYNC_NAME,
          initialized: true,
          last_created_at: nowIso,
          last_event_id: null,
          last_exported_rows: 0,
          updated_at: nowIso,
        }, { onConflict: "sync_name" });

      if (initError) {
        throw new Error(`Failed to initialize sync state: ${initError.message}`);
      }

      return jsonResponse({
        ok: true,
        initialized: true,
        skipped_history: true,
        checkpoint: nowIso,
        sheet: sheetName,
      });
    }

    let checkpointCreatedAt = (state as SyncState).last_created_at;
    let checkpointEventId = (state as SyncState).last_event_id;
    let totalExported = 0;
    let loops = 0;

    while (loops < maxLoops) {
      loops += 1;

      const { data: events, error: rpcError } = await supabase.rpc(
        "get_worklog_events_for_google_sync",
        {
          p_after_created_at: checkpointCreatedAt,
          p_after_event_id: checkpointEventId,
          p_limit: batchSize,
        },
      );

      if (rpcError) {
        throw new Error(`RPC get_worklog_events_for_google_sync failed: ${rpcError.message}`);
      }

      const batch = (events ?? []) as ExportEvent[];
      if (!batch.length) {
        break;
      }

      const rowsToAppend = batch.map((event) => eventToSheetRow(event, timeZone));
      await appendRows(googleAccessToken, spreadsheetId, sheetName, rowsToAppend);

      // Patch previously exported rows when a new event closes them.
      const closureMap = new Map<string, {
        endLocal: string;
        duration: string;
      }>();
      for (const event of batch) {
        const closesId = String(event.closes_event_id ?? "").trim();
        if (!closesId) continue;
        const endUtc = String(event.closes_event_end_ts ?? "").trim();
        if (!endUtc) continue;

        closureMap.set(closesId, {
          endLocal: formatLocalDateTime(endUtc, timeZone),
          duration: formatDuration(event.closes_event_duration_sec),
        });
      }

      if (closureMap.size > 0) {
        const eventRowMap = await getEventRowMap(
          googleAccessToken,
          spreadsheetId,
          sheetName,
        );

        const updates: Array<{ range: string; values: string[][] }> = [];
        for (const [closedEventId, closure] of closureMap.entries()) {
          const rowNumber = eventRowMap.get(closedEventId);
          if (!rowNumber) continue;
          updates.push({
            range: `'${sheetName}'!L${rowNumber}:M${rowNumber}`,
            values: [[
              closure.endLocal,
              closure.duration,
            ]],
          });
        }

        await batchUpdateValues(googleAccessToken, spreadsheetId, updates);
      }

      // When logout appears, patch shift end/duration for all rows in this session.
      const sessionClosureMap = new Map<string, { shiftEndLocal: string; shiftDuration: string }>();
      for (const event of batch) {
        if (normalizeActionType(event.action_type) !== "LOGOUT") continue;
        const sessionId = String(event.session_id ?? "").trim();
        if (!sessionId) continue;
        const shiftEndTs = String(event.shift_end_ts ?? event.event_ts ?? "").trim();
        if (!shiftEndTs) continue;
        sessionClosureMap.set(sessionId, {
          shiftEndLocal: formatLocalDateTime(shiftEndTs, timeZone),
          shiftDuration: formatDuration(event.shift_duration_sec),
        });
      }

      if (sessionClosureMap.size > 0) {
        const sessionRowMap = await getSessionRowMap(
          googleAccessToken,
          spreadsheetId,
          sheetName,
        );
        const sessionUpdates: Array<{ range: string; values: string[][] }> = [];

        for (const [sessionId, closure] of sessionClosureMap.entries()) {
          const rows = sessionRowMap.get(sessionId) ?? [];
          for (const rowNumber of rows) {
            sessionUpdates.push({
              range: `'${sheetName}'!G${rowNumber}:H${rowNumber}`,
              values: [[closure.shiftEndLocal, closure.shiftDuration]],
            });
          }
        }

        await batchUpdateValues(googleAccessToken, spreadsheetId, sessionUpdates);
      }

      const last = batch[batch.length - 1];
      checkpointCreatedAt = last.created_at;
      checkpointEventId = last.event_id;
      totalExported += batch.length;

      const { error: saveStateError } = await supabase
        .from("google_reports_sync_state")
        .upsert({
          sync_name: SYNC_NAME,
          initialized: true,
          last_created_at: checkpointCreatedAt,
          last_event_id: checkpointEventId,
          last_exported_rows: totalExported,
          updated_at: new Date().toISOString(),
        }, { onConflict: "sync_name" });

      if (saveStateError) {
        throw new Error(`Failed to save sync state: ${saveStateError.message}`);
      }

      if (batch.length < batchSize) {
        break;
      }
    }

    return jsonResponse({
      ok: true,
      exported: totalExported,
      loops,
      batch_size: batchSize,
      sheet: sheetName,
      checkpoint: {
        last_created_at: checkpointCreatedAt,
        last_event_id: checkpointEventId,
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
