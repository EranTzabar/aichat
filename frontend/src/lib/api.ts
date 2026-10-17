import type { Attachment } from "@/lib/types";

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

/** Upload a file to a work (with progress, 0..1). Returns the attachment to send in `attachment_ids`. */
export function uploadFile(workId: number, file: File, onProgress?: (fraction: number) => void): Promise<Attachment> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/works/${workId}/attachments`);
    const token = getToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total);
    xhr.onerror = () => reject(new ApiError(0, "network_error", "Can't reach the server. Is the backend running?"));
    xhr.onload = () => {
      let data: { error?: { code?: string; message?: string } } | null = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {}
      if (xhr.status >= 200 && xhr.status < 300) return resolve(data as Attachment);
      const code = data?.error?.code ?? "http_error";
      if (xhr.status === 401 && SESSION_ENDING.has(code)) window.dispatchEvent(new Event(LOGOUT_EVENT));
      reject(new ApiError(xhr.status, code, data?.error?.message ?? `Upload failed (${xhr.status})`));
    };
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

const blobUrls = new Map<number, Promise<string>>();

/** A local URL for an attachment's bytes, downloaded once with the login token (files have no public links). */
export function attachmentUrl(id: number): Promise<string> {
  let url = blobUrls.get(id);
  if (!url) {
    url = (async () => {
      const token = getToken();
      let res: Response;
      try {
        res = await fetch(`${API_URL}/attachments/${id}/file`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
      } catch {
        throw new ApiError(0, "network_error", "Can't reach the server. Is the backend running?");
      }
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new ApiError(res.status, data?.error?.code ?? "http_error", data?.error?.message ?? "Can't load the file.");
      }
      return URL.createObjectURL(await res.blob());
    })();
    url.catch(() => blobUrls.delete(id)); // let a later attempt retry
    blobUrls.set(id, url);
  }
  return url;
}

/** Save an attachment to the user's computer. */
export async function downloadAttachment(a: Attachment): Promise<void> {
  const link = document.createElement("a");
  link.href = await attachmentUrl(a.id);
  link.download = a.filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

export function fileSize(n: number): string {
  if (n < 1024) return `${n} B`;
  const units = ["KB", "MB", "GB"];
  let v = n / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v < 10 ? v.toFixed(1) : Math.round(v)} ${units[i]}`;
}
