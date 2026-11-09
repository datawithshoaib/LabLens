import { getToken } from "next-auth/jwt";
import type { NextRequest } from "next/server";
import { getValidAccessToken } from "@/lib/token-store";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function allowedRoute(method: string, segments: string[]): string | null {
  if (segments[0] !== "reports") return null;
  if (segments.length === 1) return method === "GET" || method === "POST" ? "/reports" : null;
  if (!UUID.test(segments[1])) return null;
  if (segments.length === 2 && ["GET", "DELETE"].includes(method)) {
    return `/reports/${segments[1]}`;
  }
  if (segments.length === 3 && segments[2] === "document" && method === "GET") {
    return `/reports/${segments[1]}/document`;
  }
  if (segments.length === 3 && segments[2] === "retry" && method === "POST") {
    return `/reports/${segments[1]}/retry`;
  }
  if (segments.length === 3 && segments[2] === "results" && ["GET", "POST"].includes(method)) {
    return `/reports/${segments[1]}/results`;
  }
  if (
    segments.length === 4 &&
    segments[2] === "results" &&
    UUID.test(segments[3]) &&
    method === "PATCH"
  ) {
    return `/reports/${segments[1]}/results/${segments[3]}`;
  }
  if (
    segments.length === 5 &&
    segments[2] === "results" &&
    UUID.test(segments[3]) &&
    segments[4] === "confirm" &&
    method === "POST"
  ) {
    return `/reports/${segments[1]}/results/${segments[3]}/confirm`;
  }
  return null;
}

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  if (["POST", "PATCH", "DELETE"].includes(request.method)) {
    const origin = request.headers.get("origin");
    const configuredOrigin = process.env.AUTH_URL;
    if (!origin || !configuredOrigin || origin !== new URL(configuredOrigin).origin) {
      return Response.json({ detail: "Request origin is not allowed" }, { status: 403 });
    }
  }
  const segments = (await context.params).path;
  const upstreamPath = allowedRoute(request.method, segments);
  if (!upstreamPath) return Response.json({ detail: "Not found" }, { status: 404 });

  const token = await getToken({
    req: request,
    secret: process.env.AUTH_SECRET,
    secureCookie: process.env.NODE_ENV === "production",
  });
  if (typeof token?.webSessionId !== "string") {
    return Response.json({ detail: "Sign in to continue" }, { status: 401 });
  }
  let apiAccessToken: string | null;
  try {
    apiAccessToken = await getValidAccessToken(token.webSessionId);
  } catch {
    return Response.json({ detail: "Report service is unavailable" }, { status: 503 });
  }
  if (!apiAccessToken) {
    return Response.json({ detail: "Your sign-in expired. Please sign in again." }, { status: 401 });
  }

  const baseUrl = process.env.API_INTERNAL_URL;
  if (!baseUrl) return Response.json({ detail: "Report service is unavailable" }, { status: 503 });

  const headers = new Headers({ Authorization: `Bearer ${apiAccessToken}` });
  for (const header of ["content-type", "content-length"]) {
    const value = request.headers.get(header);
    if (value) headers.set(header, value);
  }
  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  const init: RequestInit & { duplex?: "half" } = {
    method: request.method,
    headers,
    cache: "no-store",
    signal: AbortSignal.timeout(130_000),
    ...(hasBody ? { body: request.body, duplex: "half" } : {}),
  };

  try {
    const query = new URL(request.url).search;
    const upstream = await fetch(`${baseUrl}${upstreamPath}${query}`, init);
    const responseHeaders = new Headers({
      "Cache-Control": "private, no-store",
      "X-Content-Type-Options": "nosniff",
    });
    for (const header of ["content-type", "content-disposition", "x-request-id", "retry-after"]) {
      const value = upstream.headers.get(header);
      if (value) responseHeaders.set(header, value);
    }
    return new Response(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return Response.json({ detail: "Report service is unavailable" }, { status: 502 });
  }
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
