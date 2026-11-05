export const API_BASE = "/api/v1";
const TOKEN_KEY = "agenthub.token";
const REFRESH_KEY = "agenthub.refresh";

export function getToken(): string | null {
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}

export function setRefreshToken(token: string): void {
  window.localStorage.setItem(REFRESH_KEY, token);
}

export function clearRefreshToken(): void {
  window.localStorage.removeItem(REFRESH_KEY);
}

export class ApiError extends Error {
  code: string;
  status: number;
  details: Record<string, unknown>;

  constructor(code: string, status: number, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  _retry?: boolean;
}

function buildQuery(query?: RequestOptions["query"]): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    params.set(key, String(value));
  }
  const encoded = params.toString();
  return encoded ? `?${encoded}` : "";
}

let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}${buildQuery(options.query)}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch {
    throw new ApiError("NETWORK_ERROR", 0, "Network request failed");
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const raw = await response.text();
  let payload: unknown = null;
  if (raw) {
    try {
      payload = JSON.parse(raw);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    const error = (payload as { error?: { code?: string; message?: string; details?: unknown } })?.error;
    const code = error?.code ?? "UNKNOWN";
    if (response.status === 401 && path !== "/auth/refresh" && !options._retry) {
      const refreshToken = window.localStorage.getItem(REFRESH_KEY);
      if (refreshToken) {
        try {
          const refreshResponse = await fetch(`${API_BASE}/auth/refresh`, {
            method: "POST",
            headers: { Accept: "application/json", "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: refreshToken }),
          });
          if (refreshResponse.ok) {
            const refreshed = (await refreshResponse.json()) as {
              access_token: string;
              refresh_token?: string | null;
            };
            setToken(refreshed.access_token);
            if (refreshed.refresh_token) setRefreshToken(refreshed.refresh_token);
            return request<T>(path, { ...options, _retry: true });
          }
        } catch {
          /* fall through to the normal unauthorized path */
        }
      }
    }
    if (response.status === 401) {
      clearToken();
      clearRefreshToken();
      onUnauthorized?.();
    }
    throw new ApiError(
      code,
      response.status,
      error?.message ?? `HTTP ${response.status}`,
      (error?.details as Record<string, unknown>) ?? {},
    );
  }

  return payload as T;
}
