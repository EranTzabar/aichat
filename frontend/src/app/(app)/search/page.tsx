"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { FileText, MessageSquare, Paperclip, Search } from "lucide-react";
import { Avatar } from "@/components/avatar";
import { MentionText } from "@/components/mention";
import { Input } from "@/components/ui/input";
import { api, errorMessage, fileSize } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { timeAgo } from "@/lib/format";
import type { GroupRef, Person, SearchHit, SearchResults, SearchType } from "@/lib/types";
import { cn } from "@/lib/utils";

const PAGE = 20;
const TYPES: { value: SearchType; label: string }[] = [
  { value: "all", label: "Everything" },
  { value: "messages", label: "Messages" },
  { value: "chats", label: "Chats" },
  { value: "files", label: "Files" },
];

/** The snippet with the matched words (between « and ») highlighted. */
function Snippet({ text }: { text: string }) {
  const parts = text.split(/«|»/);
  return (
    <p className="line-clamp-3 text-sm whitespace-pre-line text-muted-foreground">
      {parts.map((p, i) =>
        i % 2 ? (
          <mark key={i} className="rounded bg-yellow-200 px-0.5 text-foreground dark:bg-yellow-500/40">
            {p}
          </mark>
        ) : (
          <MentionText key={i} text={p} />
        ),
      )}
    </p>
  );
}

function hitHref(h: SearchHit): string {
  return h.message_id ? `/chats/${h.chat_id}#m${h.message_id}` : `/chats/${h.chat_id}`;
}

function Hit({ h }: { h: SearchHit }) {
  const Icon = h.type === "chat" ? FileText : h.type === "file" ? Paperclip : MessageSquare;
  const what =
    h.type === "chat"
      ? "Chat post"
      : h.type === "file"
        ? `File${h.message_id ? ` in #${h.message_id}` : " on the chat post"}`
        : `Message #${h.message_id}`;
  return (
    <Link href={hitHref(h)} className="block rounded-xl border bg-card p-4 transition-colors hover:bg-muted/60">
      <div className="mb-1 flex items-center gap-2 text-xs text-muted-foreground">
        <Icon className="size-3.5 shrink-0" />
        <span className="truncate">
          {what} · {h.group.name} · <span className="font-medium text-foreground">{h.chat_title}</span>
        </span>
      </div>
      {h.attachment && (
        <div className="mb-1 truncate text-sm font-medium">
          📎 {h.attachment.filename} <span className="text-xs text-muted-foreground">({fileSize(h.attachment.size)})</span>
        </div>
      )}
      <Snippet text={h.snippet} />
      <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
        <Avatar user={h.author} size={18} />
        {h.author.display_name} · {timeAgo(h.created_at)}
      </div>
    </Link>
  );
}

function SearchPage() {
  const me = useMe();
  const router = useRouter();
  const params = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const [type, setType] = useState<SearchType>((params.get("type") as SearchType) || "all");
  const [groupId, setGroupId] = useState(params.get("group") ?? "");
  const [authorId, setAuthorId] = useState(params.get("from") ?? "");
  const [data, setData] = useState<SearchResults | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [groups, setGroups] = useState<GroupRef[]>(me.groups);
  const [people, setPeople] = useState<Person[]>([]);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    input.current?.focus();
    api<Person[]>("/people").then(setPeople).catch(() => {});
    if (me.is_admin) api<GroupRef[]>("/admin/groups").then(setGroups).catch(() => {});
  }, [me.is_admin]);

  // The search box in the menu (or Ctrl+K) can change the query while this page is open.
  useEffect(() => {
    const fromUrl = params.get("q") ?? "";
    setQ((cur) => (cur.trim() === fromUrl ? cur : fromUrl));
    input.current?.focus();
  }, [params]);

  function query(offset: number): string {
    const p = new URLSearchParams({ q: q.trim(), type, limit: String(PAGE), offset: String(offset) });
    if (groupId) p.set("group_id", groupId);
    if (authorId) p.set("author_id", authorId);
    return `/search?${p}`;
  }

  // Search as you type (after a short pause), and keep the URL shareable.
  useEffect(() => {
    const url = new URLSearchParams();
    if (q.trim()) url.set("q", q.trim());
    if (type !== "all") url.set("type", type);
    if (groupId) url.set("group", groupId);
    if (authorId) url.set("from", authorId);
    const next = `/search${url.size ? `?${url}` : ""}`;
    if (next !== `/search${params.size ? `?${params}` : ""}`) router.replace(next, { scroll: false });

    if (q.trim().length < 2) {
      setData(null);
      setError("");
      return;
    }
    let cancelled = false;
    const timer = setTimeout(() => {
      setBusy(true);
      api<SearchResults>(query(0))
        .then((d) => !cancelled && (setData(d), setError("")))
        .catch((e) => !cancelled && setError(errorMessage(e)))
        .finally(() => !cancelled && setBusy(false));
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, type, groupId, authorId]);

  async function loadMore() {
    if (!data) return;
    setBusy(true);
    try {
      const more = await api<SearchResults>(query(data.results.length));
      setData({ total: more.total, results: [...data.results, ...more.results] });
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const select = "h-8 rounded-lg border border-input bg-transparent px-2 text-sm dark:bg-input/30";
  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <h1 className="text-2xl font-semibold">Search</h1>
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          ref={input}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search messages, chats and files…"
          className="h-10 pl-8 text-base"
        />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {TYPES.map((t) => (
          <button
            key={t.value}
            onClick={() => setType(t.value)}
            className={cn(
              "rounded-full border px-3 py-1 text-sm transition-colors",
              type === t.value ? "border-primary bg-primary text-primary-foreground" : "hover:bg-muted",
            )}
          >
            {t.label}
          </button>
        ))}
        <select value={groupId} onChange={(e) => setGroupId(e.target.value)} className={select} aria-label="Group">
          <option value="">All groups</option>
          {groups.map((g) => (
            <option key={g.id} value={g.id}>
              {g.name}
            </option>
          ))}
        </select>
        <select value={authorId} onChange={(e) => setAuthorId(e.target.value)} className={select} aria-label="Person">
          <option value="">Anyone</option>
          {people.map((p) => (
            <option key={p.id} value={p.id}>
              {p.display_name}
            </option>
          ))}
        </select>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      {q.trim().length < 2 && (
        <p className="text-sm text-muted-foreground">
          Type at least 2 letters. All words must match, and word beginnings count: “plan” also finds “planning”.
        </p>
      )}
      {data && (
        <>
          <p className="text-sm text-muted-foreground">
            {data.total === 0 ? "Nothing found." : `${data.total} result${data.total === 1 ? "" : "s"}`}
            {busy && " · searching…"}
          </p>
          <div className="space-y-3">
            {data.results.map((h) => (
              <Hit key={`${h.type}-${h.attachment?.id ?? h.message_id ?? h.chat_id}`} h={h} />
            ))}
          </div>
          {data.results.length < data.total && (
            <button
              onClick={loadMore}
              disabled={busy}
              className="w-full rounded-lg border py-2 text-sm hover:bg-muted disabled:opacity-50"
            >
              {busy ? "Loading…" : "Show more"}
            </button>
          )}
        </>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <Suspense>
      <SearchPage />
    </Suspense>
  );
}
