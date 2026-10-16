"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { API_URL } from "@/lib/api";
import type { LiveEvent } from "@/lib/types";

type Listener = (e: LiveEvent) => void;
type LiveState = { connected: boolean; online: Set<number>; subscribe: (fn: Listener) => () => void };

const LiveContext = createContext<LiveState | null>(null);

/** One WebSocket per tab; components subscribe to the events they care about. */
export function LiveProvider({ token, children }: { token: string; children: React.ReactNode }) {
  const listeners = useRef(new Set<Listener>());
  const [connected, setConnected] = useState(false);
  const [online, setOnline] = useState<Set<number>>(new Set());

  useEffect(() => {
    let ws: WebSocket | null = null;
    let retry = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let ping: ReturnType<typeof setInterval> | undefined;
    let closed = false;

    const connect = () => {
      ws = new WebSocket(`${API_URL.replace(/^http/, "ws")}/ws?token=${encodeURIComponent(token)}`);
      ws.onopen = () => {
        retry = 0;
        setConnected(true);
        ping = setInterval(() => ws?.readyState === WebSocket.OPEN && ws.send("ping"), 25000);
      };
      ws.onmessage = (msg) => {
        const event = JSON.parse(msg.data) as LiveEvent;
        if (event.type === "hello") setOnline(new Set(event.online_user_ids));
        if (event.type === "presence.changed")
          setOnline((prev) => {
            const next = new Set(prev);
            if (event.online) next.add(event.user_id);
            else next.delete(event.user_id);
            return next;
          });
        listeners.current.forEach((fn) => fn(event));
      };
      ws.onclose = () => {
        setConnected(false);
        clearInterval(ping);
        if (closed) return;
        timer = setTimeout(connect, Math.min(1000 * 2 ** retry++, 15000));
      };
    };
    // Deferred so React's dev double-mount cancels it before a socket is opened.
    timer = setTimeout(connect, 0);
    return () => {
      closed = true;
      clearTimeout(timer);
      clearInterval(ping);
      ws?.close();
    };
  }, [token]);

  const subscribe = useCallback((fn: Listener) => {
    listeners.current.add(fn);
    return () => {
      listeners.current.delete(fn);
    };
  }, []);

  return <LiveContext.Provider value={{ connected, online, subscribe }}>{children}</LiveContext.Provider>;
}

export function useLive(): LiveState {
  const ctx = useContext(LiveContext);
  if (!ctx) throw new Error("useLive must be used inside LiveProvider");
  return ctx;
}

/** Subscribe to live events; the handler may change between renders. */
export function useLiveEvent(handler: Listener) {
  const { subscribe } = useLive();
  const ref = useRef(handler);
  useEffect(() => {
    ref.current = handler;
  });
  useEffect(() => subscribe((e) => ref.current(e)), [subscribe]);
}
