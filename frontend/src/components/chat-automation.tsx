"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { CalendarClock, Repeat as RepeatIcon, X } from "lucide-react";
import { Avatar } from "@/components/avatar";
import { Mention } from "@/components/mention";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { dateTime } from "@/lib/format";
import { usePeople } from "@/lib/people";
import type { Repeat, Chat } from "@/lib/types";
import { cn } from "@/lib/utils";

export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

const SELECT_CLASS =
  "h-8 rounded-lg border border-input bg-input/30 px-2.5 text-sm text-foreground outline-none " +
  "focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

/** "every day at 09:00" / "every Monday at 09:00". */
export function repeatText(r: Repeat): string {
  return `${r.every === "weekly" ? `every ${WEEKDAYS[r.weekday ?? 0]}` : "every day"} at ${r.time}`;
}

export type CloseMode = "never" | "days" | "at";

export type AutomationValues = {
  tagged_user_ids: number[];
  repeat: Repeat | null;
  close: CloseMode;
  close_after_days: number;
  /** A datetime-local value (the viewer's time). */
  close_at: string;
};

export const NO_AUTOMATION: AutomationValues = {
  tagged_user_ids: [],
  repeat: null,
  close: "never",
  close_after_days: 7,
  close_at: "",
};

/** An ISO time as a datetime-local value in the viewer's time zone. */
function toLocalInput(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function automationOf(w: Chat): AutomationValues {
  return {
    tagged_user_ids: w.tagged.map((u) => u.id),
    repeat: w.repeat,
    close: w.close_at ? "at" : "never",
    close_after_days: 7,
    close_at: w.close_at ? toLocalInput(w.close_at) : "",
  };
}

/** The automation fields for POST/PATCH /admin/chats. A repeating chat closes through its copies instead. */
export function automationPayload(a: AutomationValues): Record<string, unknown> {
  const out: Record<string, unknown> = { tagged_user_ids: a.tagged_user_ids, repeat: a.repeat };
  if (a.repeat || a.close === "never") out.close_at = null;
  else if (a.close === "days") out.close_after_days = a.close_after_days;
  else out.close_at = a.close_at ? new Date(a.close_at).toISOString() : null;
  return out;
}

/** Pick people/AIs to tag: chips of the chosen ones and a search box listing everyone. */
function TagPicker({ value, onChange }: { value: number[]; onChange: (ids: number[]) => void }) {
  const people = usePeople();
  const [q, setQ] = useState("");
  const chosen = value.map((id) => people.find((p) => p.id === id)).filter((p) => p !== undefined);
  const matches = useMemo(() => {
    const lower = q.trim().toLowerCase();
    if (!lower) return [];
    return people
      .filter((p) => p.active && !value.includes(p.id))
      .filter((p) => p.username.toLowerCase().includes(lower) || p.display_name.toLowerCase().includes(lower))
      .slice(0, 6);
  }, [people, q, value]);

  return (
    <div className="space-y-2">
      {chosen.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {chosen.map((p) => (
            <span key={p.id} className="inline-flex items-center gap-1 rounded-full border py-0.5 pr-1 pl-0.5 text-sm">
              <Avatar user={p} size={20} />
              <Mention user={p} />
              <button
                type="button"
                onClick={() => onChange(value.filter((id) => id !== p.id))}
                className="rounded-full p-0.5 hover:bg-muted"
                title="Remove"
              >
                <X className="size-3" />
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="relative">
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              if (matches[0]) {
                onChange([...value, matches[0].id]);
                setQ("");
              }
            }
          }}
          placeholder="Search people or AIs to tag…"
        />
        {matches.length > 0 && (
          <ul className="absolute z-20 mt-1 w-full rounded-lg border bg-popover p-1 shadow-md">
            {matches.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  onClick={() => {
                    onChange([...value, p.id]);
                    setQ("");
                  }}
                  className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
                >
                  <Avatar user={p} size={22} />
                  <span className="flex-1 truncate">{p.display_name}</span>
                  <span className="text-xs text-muted-foreground">@{p.username}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

/** Tags, repeat and auto-close settings of a chat (create and edit). */
export function AutomationFields({
  value,
  onChange,
}: {
  value: AutomationValues;
  onChange: (v: AutomationValues) => void;
}) {
  const set = (patch: Partial<AutomationValues>) => onChange({ ...value, ...patch });
  const r = value.repeat;
  const setRepeat = (patch: Partial<Repeat>) => set({ repeat: { ...(r ?? { every: "daily", time: "09:00" }), ...patch } });

  return (
    <fieldset className="space-y-4 rounded-lg border p-4">
      <legend className="px-1 text-sm font-medium">Automation</legend>

      <div className="space-y-1.5">
        <Label>Tag people</Label>
        <TagPicker value={value.tagged_user_ids} onChange={(tagged_user_ids) => set({ tagged_user_ids })} />
        <p className="text-xs text-muted-foreground">
          They get it as a mention (an “@ You” badge, and MENTIONS YOU for their AI) until they open the chat.
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="repeat">Repeat</Label>
        <div className="flex flex-wrap items-center gap-2">
          <select
            id="repeat"
            value={r?.every ?? "off"}
            onChange={(e) => {
              const every = e.target.value;
              if (every === "off") set({ repeat: null });
              else setRepeat({ every: every as Repeat["every"], weekday: every === "weekly" ? (r?.weekday ?? 0) : undefined });
            }}
            className={SELECT_CLASS}
          >
            <option value="off">Doesn&apos;t repeat</option>
            <option value="daily">Every day</option>
            <option value="weekly">Every week</option>
          </select>
          {r?.every === "weekly" && (
            <select
              value={r.weekday ?? 0}
              onChange={(e) => setRepeat({ weekday: Number(e.target.value) })}
              className={SELECT_CLASS}
              aria-label="Day"
            >
              {WEEKDAYS.map((d, i) => (
                <option key={d} value={i}>
                  {d}
                </option>
              ))}
            </select>
          )}
          {r && (
            <>
              <span className="text-sm text-muted-foreground">at</span>
              <Input
                type="time"
                value={r.time}
                onChange={(e) => setRepeat({ time: e.target.value })}
                className="w-28"
                aria-label="Time"
                required
              />
            </>
          )}
        </div>
        {r && (
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-muted-foreground">Close each copy after</span>
            <Input
              type="number"
              min={1}
              max={365}
              value={r.close_after_days ?? ""}
              onChange={(e) => setRepeat({ close_after_days: e.target.value ? Number(e.target.value) : undefined })}
              className="w-20"
              aria-label="Days"
              placeholder="—"
            />
            <span className="text-muted-foreground">days (optional)</span>
          </div>
        )}
        <p className="text-xs text-muted-foreground">
          {r
            ? `A copy “title – date” opens ${repeatText(r)} (server time) and the previous copy closes.`
            : "Open a fresh copy of this chat every day or week."}
        </p>
      </div>

      {!r && (
        <div className="space-y-1.5">
          <Label htmlFor="close">Close automatically</Label>
          <div className="flex flex-wrap items-center gap-2">
            <select
              id="close"
              value={value.close}
              onChange={(e) => set({ close: e.target.value as CloseMode })}
              className={SELECT_CLASS}
            >
              <option value="never">Never</option>
              <option value="days">After some days</option>
              <option value="at">At a date and time</option>
            </select>
            {value.close === "days" && (
              <>
                <Input
                  type="number"
                  min={1}
                  max={365}
                  value={value.close_after_days}
                  onChange={(e) => set({ close_after_days: Number(e.target.value) })}
                  className="w-20"
                  aria-label="Days"
                  required
                />
                <span className="text-sm text-muted-foreground">days from now</span>
              </>
            )}
            {value.close === "at" && (
              <Input
                type="datetime-local"
                value={value.close_at}
                onChange={(e) => set({ close_at: e.target.value })}
                className="w-56"
                aria-label="Close at"
                required
              />
            )}
          </div>
        </div>
      )}
    </fieldset>
  );
}

/** Who's tagged, how the chat repeats and when it closes, under the chat's title (for everyone). */
export function AutomationBadges({ chat }: { chat: Chat }) {
  const parts = [];
  if (chat.tagged.length > 0)
    parts.push(
      <span key="tagged">
        Tagged:{" "}
        {chat.tagged.map((u, i) => (
          <span key={u.id}>
            {i > 0 && ", "}
            <Mention user={u} />
          </span>
        ))}
      </span>,
    );
  if (chat.repeat)
    parts.push(
      <span key="repeat" className="inline-flex items-center gap-1">
        <RepeatIcon className="size-3.5" /> Repeats {repeatText(chat.repeat)}
        {chat.next_copy_at && ` · next ${dateTime(chat.next_copy_at)}`}
      </span>,
    );
  if (chat.close_at && chat.status === "open")
    parts.push(
      <span key="close" className="inline-flex items-center gap-1">
        <CalendarClock className="size-3.5" /> Closes {dateTime(chat.close_at)}
      </span>,
    );
  if (chat.series)
    parts.push(
      <span key="series">
        Part of{" "}
        <Link href={`/chats/${chat.series.id}`} className="text-primary hover:underline">
          {chat.series.title}
        </Link>
      </span>,
    );
  if (chat.copies.length > 0)
    parts.push(
      <span key="copies">
        Copies:{" "}
        {chat.copies.map((c, i) => (
          <span key={c.id}>
            {i > 0 && ", "}
            <Link href={`/chats/${c.id}`} className="text-primary hover:underline">
              #{c.id}
            </Link>
          </span>
        ))}
      </span>,
    );
  if (parts.length === 0) return null;
  return <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">{parts}</div>;
}
