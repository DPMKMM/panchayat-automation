const PORTAL_URL = "https://epanchayat.telangana.gov.in/epmis/allgpdata.jsp";
const MIN_WORKBOOK_BYTES = 50_000;
const PORTAL_HOSTS = new Set([
  "epanchayat.telangana.gov.in",
  "tgprepanchayat.telangana.gov.in",
]);

function json(body, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store, no-cache, must-revalidate",
      ...extraHeaders,
    },
  });
}

async function proxyPortalRequest(request, env) {
  const expectedToken = env.DCB_PROXY_TOKEN;
  const authorization = request.headers.get("authorization") ?? "";
  if (!expectedToken || authorization !== `Bearer ${expectedToken}`) {
    return json({ error: "Unauthorized" }, 401);
  }

  const targetValue = request.headers.get("x-portal-target") ?? "";
  let target;
  try {
    target = new URL(targetValue);
  } catch {
    return json({ error: "A valid e-Panchayat target URL is required." }, 400);
  }
  if (target.protocol !== "https:" || !PORTAL_HOSTS.has(target.hostname.toLowerCase()) || target.username || target.password) {
    return json({ error: "The requested host is not an allowed e-Panchayat portal." }, 403);
  }

  const method = request.method.toUpperCase();
  const headers = new Headers(request.headers);
  const portalAuthorization = headers.get("x-portal-authorization");
  for (const name of [
    "authorization", "x-portal-target", "x-portal-authorization", "host",
    "content-length", "connection", "transfer-encoding", "accept-encoding",
  ]) {
    headers.delete(name);
  }
  if (portalAuthorization) headers.set("authorization", portalAuthorization);

  try {
    const upstream = await fetch(target.toString(), {
      method,
      headers,
      body: method === "GET" || method === "HEAD" ? undefined : request.body,
      redirect: "manual",
      cf: { cacheEverything: false, cacheTtl: 0 },
    });
    const responseHeaders = new Headers(upstream.headers);
    for (const name of [
      "content-encoding", "content-length", "connection", "keep-alive",
      "transfer-encoding", "upgrade", "cf-ray", "cf-cache-status",
    ]) {
      responseHeaders.delete(name);
    }
    const cookies = typeof upstream.headers.getSetCookie === "function"
      ? upstream.headers.getSetCookie()
      : [];
    if (cookies.length) {
      responseHeaders.delete("set-cookie");
      for (const cookie of cookies) responseHeaders.append("set-cookie", cookie);
    }
    responseHeaders.set("cache-control", "no-store, no-cache, must-revalidate");
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    console.error("Live e-Panchayat browser request failed", error?.name ?? "Error", target.hostname);
    return json({ error: "Could not connect to the live e-Panchayat portal." }, 502);
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/health" && request.method === "GET") {
      return json({
        status: "ok",
        service: "e-Panchayat live DCB proxy",
        colo: request.cf?.colo ?? "unknown",
      });
    }

    if (url.pathname === "/v1/portal") {
      if (!["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"].includes(request.method)) {
        return json({ error: "Method not allowed" }, 405);
      }
      return proxyPortalRequest(request, env);
    }

    if (url.pathname !== "/v1/dcb/raw") {
      return json({ error: "Not found" }, 404);
    }
    if (request.method !== "GET") {
      return json({ error: "Method not allowed" }, 405, { allow: "GET" });
    }

    const expectedToken = env.DCB_PROXY_TOKEN;
    const authorization = request.headers.get("authorization") ?? "";
    if (!expectedToken || authorization !== `Bearer ${expectedToken}`) {
      return json({ error: "Unauthorized" }, 401);
    }

    try {
      const upstream = await fetch(PORTAL_URL, {
        method: "GET",
        headers: {
          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
          "Accept": "application/vnd.ms-excel,application/octet-stream,*/*",
          "Cache-Control": "no-cache",
          "Pragma": "no-cache",
        },
        redirect: "follow",
        cf: { cacheEverything: false, cacheTtl: 0 },
      });

      if (!upstream.ok) {
        console.error("e-Panchayat DCB fetch returned HTTP", upstream.status);
        return json({ error: "The e-Panchayat portal did not return a successful response." }, 502);
      }

      const content = await upstream.arrayBuffer();
      const contentType = (upstream.headers.get("content-type") ?? "").toLowerCase();
      if (content.byteLength < MIN_WORKBOOK_BYTES || (!contentType.includes("excel") && !contentType.includes("octet-stream"))) {
        console.error("e-Panchayat DCB response failed workbook validation", content.byteLength, contentType);
        return json({ error: "The e-Panchayat portal response was not a valid DCB workbook." }, 502);
      }

      return new Response(content, {
        status: 200,
        headers: {
          "content-type": upstream.headers.get("content-type") ?? "application/vnd.ms-excel",
          "content-length": String(content.byteLength),
          "cache-control": "no-store, no-cache, must-revalidate",
          "x-dcb-source": "epanchayat.telangana.gov.in",
        },
      });
    } catch (error) {
      console.error("Live e-Panchayat DCB request failed", error?.name ?? "Error");
      return json({ error: "Could not connect to the live e-Panchayat portal." }, 502);
    }
  },
};
