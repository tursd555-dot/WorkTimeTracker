const SYNC_SECRET = Deno.env.get("SYNC_WEBHOOK_SECRET") ?? "";

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload, null, 2), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
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

    const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";
    const projectHost = supabaseUrl
      ? new URL(supabaseUrl).host
      : null;

    return jsonResponse({
      ok: true,
      service: "healthz",
      timestamp: new Date().toISOString(),
      project_host: projectHost,
      region: Deno.env.get("SB_REGION") ?? null,
    });
  } catch (error) {
    return jsonResponse(
      { ok: false, error: String(error) },
      500,
    );
  }
});
