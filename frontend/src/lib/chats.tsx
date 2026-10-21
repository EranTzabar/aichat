"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useLiveEvent } from "@/lib/live";
import type { ChatListItem } from "@/lib/types";

type ChatsState = { chats: ChatListItem[] | null; error: string | null; refresh: () => void };

const ChatsContext = createContext<ChatsState | null>(null);

/** All chats I can access (one list; pages split it by `joined` / group). Refreshes on live events. */
export function ChatsProvider({ children }: { children: React.ReactNode }) {
  const { refreshMe } = useAuth();
  const [chats, setChats] = useState<ChatListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const load = useCallback(() => {
    api<ChatListItem[]>("/chats?limit=500")
      .then((w) => {
        setChats(w);
        setError(null);
      })
      .catch((e) => setError(e.message));
  }, []);

  const refresh = useCallback(() => {
    clearTimeout(timer.current);
    timer.current = setTimeout(load, 250);
  }, [load]);

  useEffect(() => {
    load();
    return () => clearTimeout(timer.current);
  }, [load]);

  useLiveEvent((e) => {
    if (e.type === "presence.changed" || e.type === "hello") return;
    if (e.type === "access.revoked" || e.type === "groups.changed" || e.type === "group.deleted") {
      refreshMe().catch(() => {});
    }
    refresh();
  });

  return <ChatsContext.Provider value={{ chats, error, refresh }}>{children}</ChatsContext.Provider>;
}

export function useChats(): ChatsState {
  const ctx = useContext(ChatsContext);
  if (!ctx) throw new Error("useChats must be used inside ChatsProvider");
  return ctx;
}
