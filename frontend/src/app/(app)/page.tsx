"use client";

import { ChatSection } from "@/components/chat-card";
import { useMe } from "@/lib/auth";
import { useChats } from "@/lib/chats";

export default function HomePage() {
  const me = useMe();
  const { chats, error } = useChats();

  return (
    <div className="mx-auto max-w-2xl space-y-8 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Hi, {me.display_name}</h1>
        <p className="text-sm text-muted-foreground">Your latest group chats, updated live.</p>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {chats === null ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : (
        <>
          <ChatSection
            title="My active chats"
            chats={chats.filter((w) => w.joined)}
            empty="You haven't written in any chat yet."
          />
          <ChatSection
            title="New in my groups"
            chats={chats.filter((w) => !w.joined)}
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
