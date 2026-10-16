"use client";

import { createContext, useContext, useEffect, useState } from "react";

/** Lets a page tell the right column which group's members to show. */
type PanelState = { groupId: number | null; setGroupId: (id: number | null) => void };
const PanelContext = createContext<PanelState>({ groupId: null, setGroupId: () => {} });

export function PanelProvider({ children }: { children: React.ReactNode }) {
  const [groupId, setGroupId] = useState<number | null>(null);
  return <PanelContext.Provider value={{ groupId, setGroupId }}>{children}</PanelContext.Provider>;
}

export function usePanel() {
  return useContext(PanelContext);
}

export function usePanelGroup(groupId: number | null) {
  const { setGroupId } = usePanel();
  useEffect(() => {
    setGroupId(groupId);
    return () => setGroupId(null);
  }, [groupId, setGroupId]);
}
