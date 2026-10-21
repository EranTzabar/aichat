"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Person, UserRef } from "@/lib/types";

/** Tags in text: `<@7>` (picked from the @ list, by user id) or `@username`. */
export const TAG_RE = /<@(\d+)>|(?<![\w@<])@([A-Za-z0-9_.-]+)/g;

export const tag = (id: number) => `<@${id}>`;

/** Every tag in `text`. A new regex each time: a shared one keeps its position (lastIndex) from earlier searches. */
export const findTags = (text: string) => text.matchAll(new RegExp(TAG_RE.source, "g"));

let cache: Person[] | null = null;
let loading: Promise<Person[]> | null = null;
let loadedAt = 0;

function load(): Promise<Person[]> {
  if (!loading || Date.now() - loadedAt > 60_000) {
    loadedAt = Date.now();
    loading = api<Person[]>("/people?everyone=true").then((p) => (cache = p));
    loading.catch(() => (loading = null));
  }
  return loading;
}

/** Everyone on the site (for the @ list and for showing tags), shared by all components. */
export function usePeople(): Person[] {
  const [people, setPeople] = useState<Person[]>(cache ?? []);
  useEffect(() => {
    let live = true;
    load()
      .then((p) => live && setPeople(p))
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);
  return people;
}

export type PeopleIndex = { byId: Map<number, UserRef>; byName: Map<string, UserRef> };

export function indexPeople(...lists: (UserRef[] | undefined)[]): PeopleIndex {
  const byId = new Map<number, UserRef>();
  const byName = new Map<string, UserRef>();
  for (const list of lists)
    for (const u of list ?? []) {
      byId.set(u.id, u);
      byName.set(u.username.toLowerCase(), u);
    }
  return { byId, byName };
}

/** The user a tag match (from TAG_RE) points to, or null. `@dana.` also finds `dana`. */
export function resolveTag(index: PeopleIndex, id: string | undefined, name: string | undefined): UserRef | null {
  if (id) return index.byId.get(Number(id)) ?? null;
  if (!name) return null;
  const lower = name.toLowerCase();
  return index.byName.get(lower) ?? index.byName.get(lower.replace(/[.-]+$/, "")) ?? null;
}

/** The text with tags of known users as `{user, text}` parts, the rest as plain strings. */
export function splitTags(text: string, index: PeopleIndex): (string | { user: UserRef; raw: string })[] {
  const out: (string | { user: UserRef; raw: string })[] = [];
  let last = 0;
  for (const m of findTags(text)) {
    const user = resolveTag(index, m[1], m[2]);
    if (!user) continue;
    // `@dana.`: the tag is `@dana`, the dot stays text.
    const raw = m[2] && m[2].toLowerCase() !== user.username.toLowerCase() ? `@${m[2].slice(0, user.username.length)}` : m[0];
    out.push(text.slice(last, m.index), { user, raw });
    last = m.index + raw.length;
  }
  out.push(text.slice(last));
  return out.filter((p) => p !== "");
}
