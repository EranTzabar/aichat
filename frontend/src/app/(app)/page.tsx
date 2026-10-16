"use client";

import { WorkSection } from "@/components/work-card";
import { useMe } from "@/lib/auth";
import { useWorks } from "@/lib/works";

export default function HomePage() {
  const me = useMe();
  const { works, error } = useWorks();

  return (
    <div className="mx-auto max-w-2xl space-y-8 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Hi, {me.display_name}</h1>
        <p className="text-sm text-muted-foreground">Your latest group works, updated live.</p>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {works === null ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : (
        <>
          <WorkSection
            title="My active chats"
            works={works.filter((w) => w.joined)}
            empty="You haven't written in any work yet."
          />
          <WorkSection
            title="New in my groups"
            works={works.filter((w) => !w.joined)}
            empty={
              me.groups.length || me.is_admin
                ? "Nothing new right now."
                : "You are not in any group yet. Ask the admin to add you."
            }
          />
        </>
      )}
    </div>
  );
}
