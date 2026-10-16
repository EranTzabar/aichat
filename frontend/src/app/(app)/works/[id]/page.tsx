"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Lock, Pencil } from "lucide-react";
import { Avatar } from "@/components/avatar";
import { Markdown } from "@/components/markdown";
import { NotAllowed } from "@/components/not-allowed";
import { usePanelGroup } from "@/components/panel";
import { Composer, LikeButton, MessageBubble } from "@/components/thread";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { api, ApiError, errorMessage } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { timeAgo } from "@/lib/format";
import { useLiveEvent } from "@/lib/live";
import type { LikeStatus, Likes, Message, UserRef, WorkState } from "@/lib/types";
import { useWorks } from "@/lib/works";

type ReplyTarget = { commentId: number; messageId: number; user: UserRef };

function applyLike(likes: Likes, count: number, user: UserRef, liked: boolean): Likes {
  const others = likes.users.filter((u) => u.id !== user.id);
  return { count, users: liked ? [...others, user] : others };
}

function addMessage(state: WorkState, m: Message): WorkState {
  const exists = state.messages.some((c) => c.id === m.id || c.replies?.some((r) => r.id === m.id));
  if (exists) return state;
  if (m.parent_id === null) return { ...state, messages: [...state.messages, { ...m, replies: [] }] };
  return {
    ...state,
    messages: state.messages.map((c) => (c.id === m.parent_id ? { ...c, replies: [...(c.replies ?? []), m] } : c)),
  };
}

function mapMessage(state: WorkState, id: number, fn: (m: Message) => Message): WorkState {
  return {
    ...state,
    messages: state.messages.map((c) =>
      c.id === id ? fn(c) : { ...c, replies: c.replies?.map((r) => (r.id === id ? fn(r) : r)) },
    ),
  };
}

export default function WorkPage() {
  const workId = Number(useParams<{ id: string }>().id);
  return <WorkView key={workId} workId={workId} />;
}

function WorkView({ workId }: { workId: number }) {
  const me = useMe();
  const { refresh: refreshWorks } = useWorks();
  const [state, setState] = useState<WorkState | null>(null);
  const [denied, setDenied] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [replyTarget, setReplyTarget] = useState<ReplyTarget | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const report = (e: unknown) => setFlash(errorMessage(e));
  const bottomRef = useRef<HTMLDivElement>(null);
  const readTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  usePanelGroup(state?.work.group.id ?? null);

  const markRead = useCallback(() => {
    clearTimeout(readTimer.current);
    readTimer.current = setTimeout(() => {
      api(`/works/${workId}/read`, { method: "POST" })
        .then(refreshWorks)
        .catch(() => {});
    }, 400);
  }, [workId, refreshWorks]);

  useEffect(() => {
    api<WorkState>(`/works/${workId}`)
      .then((s) => {
        setState(s);
        markRead();
      })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 403) setDenied(e.message);
        else setError(errorMessage(e));
      });
    return () => clearTimeout(readTimer.current);
  }, [workId, markRead]);

  useLiveEvent((e) => {
    if (!state) return;
    const groupId = state.work.group.id;
    if (e.type === "access.revoked" && e.group_id === groupId && !me.is_admin) {
      setDenied(`You were removed from group '${e.group_name}', so you can no longer view or post in this work.`);
      return;
    }
    if (e.type === "group.deleted" && e.group_id === groupId) {
      setDenied(`The group '${e.group_name}' was deleted together with its works.`);
      return;
    }
    if (!("work_id" in e) || e.work_id !== workId) return;
    if (e.type === "message.created") {
      setState((s) => s && addMessage(s, e.message));
      markRead();
    } else if (e.type === "like.changed") {
      const mine = e.user.id === me.id;
      setState((s) => {
        if (!s) return s;
        if (e.target_type === "work") {
          const w = s.work;
          return {
            ...s,
            work: {
              ...w,
              likes: applyLike(w.likes, e.count, e.user, e.liked),
              liked_by_me: mine ? e.liked : w.liked_by_me,
            },
          };
        }
        return mapMessage(s, e.target_id, (m) => ({
          ...m,
          likes: applyLike(m.likes, e.count, e.user, e.liked),
          liked_by_me: mine ? e.liked : m.liked_by_me,
        }));
      });
    } else if (e.type === "work.updated") {
      setState((s) => s && { ...s, work: { ...s.work, ...e.work } });
    }
  });

  async function toggleWorkLike() {
    if (!state) return;
    const liked = !state.work.liked_by_me;
    const r = await api<LikeStatus>(`/works/${workId}/like`, { method: liked ? "POST" : "DELETE" });
    setState(
      (s) =>
        s && {
          ...s,
          work: { ...s.work, likes: applyLike(s.work.likes, r.count, me, r.liked_by_me), liked_by_me: r.liked_by_me },
        },
    );
  }

  async function toggleMessageLike(m: Message) {
    const liked = !m.liked_by_me;
    const r = await api<LikeStatus>(`/messages/${m.id}/like`, { method: liked ? "POST" : "DELETE" });
    setState(
      (s) =>
        s &&
        mapMessage(s, m.id, (x) => ({
          ...x,
          likes: applyLike(x.likes, r.count, me, r.liked_by_me),
          liked_by_me: r.liked_by_me,
        })),
    );
  }

  async function postComment(body: string) {
    const m = await api<Message>(`/works/${workId}/messages`, { json: { body } });
    setState((s) => s && addMessage(s, m));
    refreshWorks();
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  }

  async function postReply(body: string) {
    if (!replyTarget) return;
    const m = await api<Message>(`/messages/${replyTarget.messageId}/replies`, {
      json: { body, reply_to_user_id: replyTarget.user.id },
    });
    setState((s) => s && addMessage(s, m));
    setReplyTarget(null);
    refreshWorks();
  }

  async function setStatus(status: "open" | "closed") {
    try {
      await api(`/admin/works/${workId}`, { method: "PATCH", json: { status } });
    } catch (e) {
      report(e);
    }
  }

  if (denied) return <NotAllowed message={denied} />;
  if (error) return <p className="p-6 text-destructive">{error}</p>;
  if (!state) return <p className="p-6 text-muted-foreground">Loading…</p>;

  const { work } = state;
  const closed = work.status === "closed";

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <article className="rounded-xl border bg-card">
        <header className="flex items-start gap-3 p-4 pb-2">
          <Avatar user={work.author} size={42} />
          <div className="min-w-0 flex-1">
            <div className="font-semibold">{work.author.display_name}</div>
            <div className="text-xs text-muted-foreground">
              <Link href={`/groups/${work.group.id}`} className="hover:underline">
                {work.group.name}
              </Link>{" "}
              · {timeAgo(work.created_at)} · work #{work.id}
            </div>
          </div>
          {closed ? (
            <Badge variant="secondary" className="gap-1">
              <Lock className="size-3" /> closed
            </Badge>
          ) : (
            <Badge variant="outline">open</Badge>
          )}
        </header>
        <div className="space-y-2 px-4 pb-3">
          <h1 className="text-xl font-semibold">{work.title}</h1>
          {work.body && <Markdown>{work.body}</Markdown>}
        </div>
        <div className="flex items-center gap-2 border-t px-2 py-1">
          <LikeButton
            size="md"
            likes={work.likes}
            liked={work.liked_by_me}
            disabled={closed}
            onToggle={() => toggleWorkLike().catch(report)}
          />
          <span className="ml-auto pr-2 text-xs text-muted-foreground">
            {state.messages.reduce((n, c) => n + 1 + (c.replies?.length ?? 0), 0)} comments
          </span>
          {me.is_admin && (
            <>
              <Link href={`/admin/works/${work.id}`} className={buttonVariants({ variant: "ghost", size: "sm" })}>
                <Pencil className="size-3.5" /> Edit
              </Link>
              <Button variant="ghost" size="sm" onClick={() => setStatus(closed ? "open" : "closed")}>
                {closed ? "Reopen" : "Close"}
              </Button>
            </>
          )}
        </div>
      </article>

      {flash && (
        <button
          onClick={() => setFlash(null)}
          className="w-full rounded-lg bg-destructive/15 p-2 text-left text-sm text-destructive"
        >
          {flash} <span className="opacity-60">(dismiss)</span>
        </button>
      )}

      {closed && (
        <div className="flex items-center gap-2 rounded-lg border border-dashed p-3 text-sm text-muted-foreground">
          <Lock className="size-4" /> This work is closed. You can read it, but no new comments or likes.
        </div>
      )}

      <div className="space-y-4">
        {state.messages.map((c) => (
          <div key={c.id} className="space-y-2">
            <MessageBubble
              message={c}
              closed={closed}
              onLike={() => toggleMessageLike(c).catch(report)}
              onReply={() => setReplyTarget({ commentId: c.id, messageId: c.id, user: c.author })}
            />
            {((c.replies?.length ?? 0) > 0 || replyTarget?.commentId === c.id) && (
              <div className="ml-11 space-y-2 border-l pl-3">
                {c.replies?.map((r) => (
                  <MessageBubble
                    key={r.id}
                    message={r}
                    small
                    closed={closed}
                    onLike={() => toggleMessageLike(r).catch(report)}
                    onReply={() => setReplyTarget({ commentId: c.id, messageId: r.id, user: r.author })}
                  />
                ))}
                {replyTarget?.commentId === c.id && !closed && (
                  <Composer
                    key={`${replyTarget.messageId}-${replyTarget.user.id}`}
                    me={me}
                    autoFocus
                    replyTo={replyTarget.user}
                    onCancelReply={() => setReplyTarget(null)}
                    placeholder={`Reply to ${replyTarget.user.display_name}…`}
                    onSend={postReply}
                  />
                )}
              </div>
            )}
          </div>
        ))}
        {state.messages.length === 0 && <p className="text-sm text-muted-foreground">No comments yet.</p>}
      </div>

      {!closed && (
        <div className="sticky bottom-0 border-t bg-background/95 py-3 backdrop-blur">
          <Composer me={me} placeholder="Write a comment…" onSend={postComment} />
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
