const BASE = "/api";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  fieldErrors?: Record<string, string>;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      const errors = (detail as { errors?: unknown }).errors;
      if (errors && typeof errors === "object" && !Array.isArray(errors)) {
        this.fieldErrors = errors as Record<string, string>;
      }
    }
  }
}

export function buildQuery(params: Record<string, unknown>): string {
  const usp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    usp.set(key, String(value));
  }
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

let csrfToken: string | null = null;

function cookieValue(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export async function fetchCsrfToken(force = false): Promise<string | null> {
  if (!force) {
    const fromCookie = cookieValue("vr_csrf");
    if (fromCookie) {
      csrfToken = fromCookie;
      return fromCookie;
    }
    if (csrfToken) return csrfToken;
  }
  const res = await fetch(`${BASE}/auth/csrf`, { credentials: "include" });
  if (!res.ok) throw new ApiError(res.status, "Could not obtain CSRF token");
  const data = (await res.json()) as { csrf_token: string };
  csrfToken = data.csrf_token ?? null;
  return csrfToken;
}

export function clearCsrfToken(): void {
  csrfToken = null;
}

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

interface RequestOptions {
  method?: HttpMethod;
  body?: unknown;
  form?: FormData;
  signal?: AbortSignal;
}

async function parseBody(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function errorMessage(status: number, data: unknown): string {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "errors" in detail) {
      const first = Object.values(detail as Record<string, string>)[0];
      return typeof first === "string" ? first : "Validation failed";
    }
  }
  return `Request failed (${status})`;
}

async function request<T>(path: string, options: RequestOptions, retried = false): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;

  if (method !== "GET") {
    const token = await fetchCsrfToken();
    if (token) headers["X-CSRF-Token"] = token;
    if (options.form) {
      body = options.form;
    } else if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(options.body);
    }
  }

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body,
    credentials: "include",
    signal: options.signal,
  });

  const data = await parseBody(res);

  if (res.status === 403 && !retried && method !== "GET") {
    const detail =
      data && typeof data === "object" && "detail" in data
        ? (data as { detail: unknown }).detail
        : undefined;
    if (detail === "csrf_failed") {
      await fetchCsrfToken(true);
      return request<T>(path, options, true);
    }
  }

  if (res.status === 401) {
    if (
      typeof window !== "undefined" &&
      !retried &&
      window.location.pathname !== "/login"
    ) {
      window.location.assign("/login");
    }
    throw new ApiError(401, typeof data === "string" && data ? data : "Not authenticated", data);
  }

  if (!res.ok) {
    throw new ApiError(res.status, errorMessage(res.status, data), 
      data && typeof data === "object" && "detail" in data
        ? (data as { detail: unknown }).detail
        : data);
  }

  return data as T;
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { signal }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  postForm: <T>(path: string, form: FormData) => request<T>(path, { method: "POST", form }),
  put: <T>(path: string, body: unknown) => request<T>(path, { method: "PUT", body }),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: "PATCH", body }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

export function apiUrl(path: string): string {
  return `${BASE}${path}`;
}
