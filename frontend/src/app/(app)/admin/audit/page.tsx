"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageHeader, useFetch } from "@/components/admin";
import { Avatar } from "@/components/avatar";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, errorMessage, fileSize } from "@/lib/api";
import { dateTime } from "@/lib/format";
import type { AdminUser, AuditEvent, AuditPage, AuditVia, Group } from "@/lib/types";

const PAGE = 50;

const ACTIONS: Record<string, string> = {
  login: "Signed in",
  "login.failed": "Failed sign-in",
  "message.create": "Posted a message",
  "attachment.upload": "Uploaded a file",
  "attachment.remove": "Removed a file",
  "chat.like": "Liked a chat",
  "chat.unlike": "Unliked a chat",
  "message.like": "Liked a message",
  "message.unlike": "Unliked a message",
  "chat.create": "Created a chat",
  "chat.update": "Edited a chat",
  "chat.close": "Closed a chat",
  "chat.reopen": "Reopened a chat",
  "user.create": "Created a user",
  "user.update": "Edited a user",
  "user.groups": "Changed a user's groups",
  "user.avatar": "Changed a user's icon",
  "user.token_view": "Viewed an API token",
  "user.token_regenerate": "Made a new API token",
  "me.avatar": "Changed own icon",
  "group.create": "Created a group",
  "group.update": "Edited a group",
  "group.delete": "Deleted a group",
  "chat.repeat": "Opened a repeating copy",
};

const CATEGORIES = [
  { value: "", label: "All actions" },
  { value: "login", label: "Sign-ins" },
  { value: "message.", label: "Messages and message likes" },
  { value: "attachment.", label: "Files" },
  { value: "chat.", label: "Chats and chat likes" },
  { value: "user.", label: "Users and tokens" },
  { value: "group.", label: "Groups" },
  { value: "me.", label: "Own icon" },
];

const VIA: Record<AuditVia, { label: string; variant: "outline" | "secondary" | "default" }> = {
  web: { label: "Website", variant: "outline" },
  api: { label: "AI / API", variant: "secondary" },
  auto: { label: "Automatic", variant: "default" },
};

function show(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  return typeof value === "string" ? value : JSON.stringify(value);
}

/** One readable line about the event's details. */
function summary(e: AuditEvent, groupName: (id: number) => string): string {
  const d = e.details as Record<string, unknown>;
  switch (e.action) {
    case "message.create":
      return `“${show(d.preview)}”${Array.isArray(d.attachment_ids) ? ` + ${d.attachment_ids.length} file(s)` : ""}`;
    case "login.failed":
      return `as “${show(d.username)}”${d.reason ? ` (${show(d.reason)})` : ""}`;
    case "attachment.upload":
      return `${show(d.filename)} (${fileSize(Number(d.size) || 0)})`;
    case "attachment.remove":
    case "chat.create":
    case "group.create":
      return show(d.filename ?? d.title ?? d.name);
    case "group.delete":
      return `${show(d.name)} with ${show(d.chats)} chat(s)`;
    case "user.create":
      return `@${show(d.username)}${d.is_admin ? " (admin)" : ""}`;
    case "user.groups": {
      const names = (v: unknown) => (Array.isArray(v) ? v.map((id) => groupName(Number(id))).join(", ") : "");
      return [d.added && names(d.added) && `added to ${names(d.added)}`, d.removed && names(d.removed) && `removed from ${names(d.removed)}`]
        .filter(Boolean)
        .join("; ");
    }
    case "chat.repeat":
      return show(d.title);
    case "user.token_regenerate":
      return `version ${show(d.token_version)}; the old token stopped working`;
  }
  // Edits: field: old → new
  return Object.entries(d)
    .map(([k, v]) => (Array.isArray(v) && v.length === 2 && k !== "attachment_ids" ? `${k}: ${show(v[0])} → ${show(v[1])}` : `${k}: ${show(v)}`))
    .join("; ");
}

function Target({ e }: { e: AuditEvent }) {
  const chatLink = (label: string, hash = "") =>
    e.chat ? (
      <Link href={`/chats/${e.chat.id}${hash}`} className="hover:underline">
        {label}
      </Link>
    ) : (
      <span className="text-muted-foreground">{label} (deleted)</span>
    );
  const title = e.chat ? `“${e.chat.title}”` : `chat #${e.chat_id}`;
  switch (e.target_type) {
    case "message":
      return chatLink(`#${e.target_id} in ${title}`, `#m${e.target_id}`);
    case "chat":
    case "attachment":
      return chatLink(e.target_type === "attachment" ? `file #${e.target_id} in ${title}` : title);
    case "user":
      return (
        <Link href={`/admin/users/${e.target_id}`} className="hover:underline">
          user #{e.target_id}
        </Link>
      );
    case "group":
      return e.group ? (
        <Link href={`/admin/groups/${e.group.id}`} className="hover:underline">
          {e.group.name}
        </Link>
      ) : (
        <span className="text-muted-foreground">group #{e.target_id} (deleted)</span>
      );
  }
  return <span className="text-muted-foreground">—</span>;
}

export default function AuditPage() {
  const users = useFetch<AdminUser[]>("/admin/users");
  const groups = useFetch<Group[]>("/admin/groups");
  const [userId, setUserId] = useState("");
  const [groupId, setGroupId] = useState("");
  const [action, setAction] = useState("");
  const [via, setVia] = useState("");
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [next, setNext] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function query(beforeId?: number): string {
    const p = new URLSearchParams({ limit: String(PAGE) });
    if (userId) p.set("user_id", userId);
    if (groupId) p.set("group_id", groupId);
    if (action) p.set("action", action);
    if (via) p.set("via", via);
    if (beforeId) p.set("before_id", String(beforeId));
    return `/admin/audit?${p}`;
  }

  async function load(more: boolean) {
    setBusy(true);
    try {
      const page = await api<AuditPage>(query(more ? (next ?? undefined) : undefined));
      setEvents((old) => (more ? [...old, ...page.events] : page.events));
      setNext(page.next_before_id);
      setError("");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, groupId, action, via]);

  const groupNames = new Map(groups.data?.map((g) => [g.id, g.name]));
  const groupName = (id: number) => groupNames.get(id) ?? `#${id}`;
  const select = "h-8 rounded-lg border border-input bg-transparent px-2 text-sm dark:bg-input/30";
  return (
    <>
      <PageHeader
        title="Audit log"
        description="Every change on the site and who made it: from the website, an AI (API key) or automatically (repeating chats, auto-close). Reading is not recorded."
      />
      <div className="flex flex-wrap items-center gap-2">
        <select value={userId} onChange={(e) => setUserId(e.target.value)} className={select} aria-label="User">
          <option value="">Everyone</option>
          {users.data?.map((u) => (
            <option key={u.id} value={u.id}>
              {u.display_name} (@{u.username})
            </option>
          ))}
        </select>
        <select value={groupId} onChange={(e) => setGroupId(e.target.value)} className={select} aria-label="Group">
          <option value="">All groups</option>
          {groups.data?.map((g) => (
            <option key={g.id} value={g.id}>
              {g.name}
            </option>
          ))}
        </select>
        <select value={action} onChange={(e) => setAction(e.target.value)} className={select} aria-label="Action">
          {CATEGORIES.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
        <select value={via} onChange={(e) => setVia(e.target.value)} className={select} aria-label="Made from">
          <option value="">Website, AI and automatic</option>
          {(Object.keys(VIA) as AuditVia[]).map((v) => (
            <option key={v} value={v}>
              {VIA[v].label}
            </option>
          ))}
        </select>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="rounded-xl border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Time</TableHead>
              <TableHead>Who</TableHead>
              <TableHead>From</TableHead>
              <TableHead>Action</TableHead>
              <TableHead>On</TableHead>
              <TableHead>Details</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {events.map((e) => (
              <TableRow key={e.id}>
                <TableCell className="text-xs whitespace-nowrap text-muted-foreground" title={e.ip ? `IP ${e.ip}` : undefined}>
                  {dateTime(e.at)}
                </TableCell>
                <TableCell>
                  {e.actor ? (
                    <Link href={`/admin/users/${e.actor.id}`} className="flex items-center gap-2 hover:underline">
                      <Avatar user={e.actor} size={22} />
                      <span className="text-sm whitespace-nowrap">{e.actor.display_name}</span>
                    </Link>
                  ) : (
                    <span className="text-sm text-muted-foreground">unknown</span>
                  )}
                </TableCell>
                <TableCell>
                  <Badge variant={VIA[e.via]?.variant ?? "outline"}>{VIA[e.via]?.label ?? e.via}</Badge>
                </TableCell>
                <TableCell className="text-sm whitespace-nowrap">
                  <span className={e.action === "login.failed" ? "text-destructive" : undefined}>
                    {ACTIONS[e.action] ?? e.action}
                  </span>
                </TableCell>
                <TableCell className="text-sm">
                  <Target e={e} />
                  {e.group && e.target_type !== "group" && (
                    <div className="text-xs text-muted-foreground">{e.group.name}</div>
                  )}
                </TableCell>
                <TableCell className="max-w-80 truncate text-xs text-muted-foreground" title={summary(e, groupName)}>
                  {summary(e, groupName)}
                </TableCell>
              </TableRow>
            ))}
            {!busy && events.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="py-6 text-center text-sm text-muted-foreground">
                  Nothing recorded yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      {next !== null && (
        <button
          onClick={() => load(true)}
          disabled={busy}
          className="w-full rounded-lg border py-2 text-sm hover:bg-muted disabled:opacity-50"
        >
          {busy ? "Loading…" : "Load more"}
        </button>
      )}
    </>
  );
}
