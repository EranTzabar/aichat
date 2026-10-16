"use client";

import { useSyncExternalStore } from "react";

// Bumped after an avatar upload so every <Avatar> refetches its image.
let version = 0;
const subs = new Set<() => void>();

export function bumpAvatarVersion() {
  version++;
  subs.forEach((fn) => fn());
}

export function useAvatarVersion(): number {
  return useSyncExternalStore(
    (fn) => {
      subs.add(fn);
      return () => subs.delete(fn);
    },
    () => version,
    () => 0,
  );
}
