"use client";

import { useMemo } from "react";
import { indexPeople, splitTags, usePeople } from "@/lib/people";
import type { UserRef } from "@/lib/types";
import { useMe } from "@/lib/auth";
import { cn } from "@/lib/utils";

export const MENTION_CLASS = "font-semibold text-blue-600 dark:text-blue-400";

/** A tagged user: the name in blue, without the @. Tags of me get a light background. */
export function Mention({ user }: { user: UserRef }) {
  const me = useMe();
  return (
    <span
      className={cn(MENTION_CLASS, user.id === me.id && "rounded bg-blue-500/15 px-0.5")}
      title={`@${user.username}`}
    >
      {user.display_name}
    </span>
  );
}

/** Plain text (a preview or snippet) with the tags of known users shown as names. */
export function MentionText({ text, mentions }: { text: string; mentions?: UserRef[] }) {
  const people = usePeople();
  const index = useMemo(() => indexPeople(people, mentions), [people, mentions]);
  return (
    <>
      {splitTags(text, index).map((part, i) =>
        typeof part === "string" ? part : <Mention key={i} user={part.user} />,
      )}
    </>
  );
}
