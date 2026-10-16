"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useLiveEvent } from "@/lib/live";
import type { WorkListItem } from "@/lib/types";

type WorksState = { works: WorkListItem[] | null; error: string | null; refresh: () => void };

const WorksContext = createContext<WorksState | null>(null);

/** All works I can access (one list; pages split it by `joined` / group). Refreshes on live events. */
export function WorksProvider({ children }: { children: React.ReactNode }) {
  const { refreshMe } = useAuth();
  const [works, setWorks] = useState<WorkListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const load = useCallback(() => {
    api<WorkListItem[]>("/works?limit=500")
      .then((w) => {
        setWorks(w);
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

  return <WorksContext.Provider value={{ works, error, refresh }}>{children}</WorksContext.Provider>;
}

export function useWorks(): WorksState {
  const ctx = useContext(WorksContext);
  if (!ctx) throw new Error("useWorks must be used inside WorksProvider");
  return ctx;
}
