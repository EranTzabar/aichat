export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8002/api/v1";
export const TOKEN_KEY = "aichat.token";
export const LOGOUT_EVENT = "aichat:logout";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

const SESSION_ENDING = new Set(["token_expired", "invalid_token", "user_disabled", "token_revoked"]);

type Options = { method?: string; json?: unknown; form?: FormData };

export async function api<T = unknown>(path: string, opts: Options = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  } else if (opts.form) {
    body = opts.form;
  }

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { method: opts.method ?? (body ? "POST" : "GET"), headers, body });
  } catch {
    throw new ApiError(0, "network_error", "Can't reach the server. Is the backend running?");
  }
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const code = data?.error?.code ?? "http_error";
    const message = data?.error?.message ?? `Request failed (${res.status})`;
    if (res.status === 401 && SESSION_ENDING.has(code)) window.dispatchEvent(new Event(LOGOUT_EVENT));
    throw new ApiError(res.status, code, message);
  }
  return data as T;
}

export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

const AVATAR_TYPES = ["image/png", "image/jpeg", "image/gif", "image/webp"];
export const MAX_AVATAR_BYTES = 2 * 1024 * 1024;

/** Same rules as the server; returns an error message, or null when the file is OK. */
export function avatarProblem(file: File): string | null {
  if (!AVATAR_TYPES.includes(file.type)) return "The icon must be a PNG, JPEG, GIF or WEBP image.";
  if (file.size > MAX_AVATAR_BYTES)
    return `The icon is ${(file.size / 1024 / 1024).toFixed(1)} MB; it must be at most 2 MB.`;
  return null;
}
