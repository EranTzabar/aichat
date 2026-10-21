"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Lock, Pencil } from "lucide-react";
import { Attachments } from "@/components/attachments";
import { Avatar } from "@/components/avatar";
import { goToMessage, Markdown } from "@/components/markdown";
import { NotAllowed } from "@/components/not-allowed";
import { usePanelGroup } from "@/components/panel";
import { Composer, LikeButton, MessageBubble } from "@/components/thread";
import { Badge } from "@/components/ui/badge";
import { AutomationBadges } from "@/components/chat-automation";
import { Button, buttonVariants } from "@/components/ui/button";
import { api, ApiError, errorMessage } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { timeAgo } from "@/lib/format";
import { useLiveEvent } from "@/lib/live";
import type { LikeStatus, Likes, Message, UserRef, ChatState } from "@/lib/types";
import { useChats } from "@/lib/chats";

// Replies nest up to three levels: comment → reply → reply.
const MAX_DEPTH = 3;

// `parentId` is the message whose replies box shows the composer (where the new reply will appear).
type ReplyTarget = { parentId: number; messageId: number; user: UserRef };

function applyLike(likes: Likes, count: number, user: UserRef, liked: boolean): Likes {
  const others = likes.users.filter((u) => u.id !== user.id);
  return { count, users: liked ? [...others, user] : others };
}

function contains(list: Message[], id: number): boolean {
  return list.some((m) => m.id === id || contains(m.replies ?? [], id));
}

function collectIds(list: Message[]): number[] {
  return list.flatMap((m) => [m.id, ...collectIds(m.replies ?? [])]);
}

function countMessages(list: Message[]): number {
  return list.reduce((n, m) => n + 1 + countMessages(m.replies ?? []), 0);
}

function mapTree(list: Message[], fn: (m: Message) => Message): Message[] {
  return list.map((m) => {
    const out = fn(m);
    return out.replies ? { ...out, replies: mapTree(out.replies, fn) } : out;
  });
}

function addMessage(state: ChatState, m: Message): ChatState {
  if (contains(state.messages, m.id)) return state;
  if (m.parent_id === null) return { ...state, messages: [...state.messages, { ...m, replies: [] }] };
  return {
    ...state,
    messages: mapTree(state.messages, (p) =>
      p.id === m.parent_id ? { ...p, replies: [...(p.replies ?? []), p.parent_id === null ? { ...m, replies: [] } : m] } : p,
    ),
  };
}

function mapMessage(state: ChatState, id: number, fn: (m: Message) => Message): ChatState {
  return { ...state, messages: mapTree(state.messages, (m) => (m.id === id ? fn(m) : m)) };
}

export default function ChatPage() {
  const chatId = Number(useParams<{ id: string }>().id);
  return <ChatView key={chatId} chatId={chatId} />;
}

function ChatView({ chatId }: { chatId: number }) {
  const me = useMe();
  const { refresh: refreshChats } = useChats();
  const [state, setState] = useState<ChatState | null>(null);
  const [denied, setDenied] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [replyTarget, setReplyTarget] = useState<ReplyTarget | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const report = (e: unknown) => setFlash(errorMessage(e));
  const bottomRef = useRef<HTMLDivElement>(null);
  const readTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  usePanelGroup(state?.chat.group.id ?? null);
  const messages = state?.messages;
  const messageIds = useMemo(() => new Set(collectIds(messages ?? [])), [messages]);

  const markRead = useCallback(() => {
    clearTimeout(readTimer.current);
    readTimer.current = setTimeout(() => {
      api(`/chats/${chatId}/read`, { method: "POST" })
        .then(refreshChats)
        .catch(() => {});
    }, 400);
  }, [chatId, refreshChats]);

  useEffect(() => {
    api<ChatState>(`/chats/${chatId}`)
      .then((s) => {
        setState(s);
        markRead();
        // A shared link like /chats/5#m123 opens at that message.
        const target = location.hash.match(/^#m(\d+)$/)?.[1];
        if (target) setTimeout(() => goToMessage(target), 100);
      })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 403) setDenied(e.message);
        else setError(errorMessage(e));
      });
    return () => clearTimeout(readTimer.current);
  }, [chatId, markRead]);

  useLiveEvent((e) => {
    if (!state) return;
    const groupId = state.chat.group.id;
    if (e.type === "access.revoked" && e.group_id === groupId && !me.is_admin) {
      setDenied(`You were removed from group '${e.group_name}', so you can no longer view or post in this chat.`);
      return;
    }
    if (e.type === "group.deleted" && e.group_id === groupId) {
      setDenied(`The group '${e.group_name}' was deleted together with its chats.`);
      return;
    }
    if (!("chat_id" in e) || e.chat_id !== chatId) return;
    if (e.type === "message.created") {
      setState((s) => s && addMessage(s, e.message));
      markRead();
    } else if (e.type === "like.changed") {
      const mine = e.user.id === me.id;
      setState((s) => {
        if (!s) return s;
        if (e.target_type === "chat") {
          const w = s.chat;
          return {
            ...s,
            chat: {
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
    } else if (e.type === "message.seen") {
      const ids = new Set(e.message_ids);
      setState(
        (s) =>
          s && {
            ...s,
            messages: mapTree(s.messages, (m) =>
              ids.has(m.id) && !(m.seen_by ?? []).some((u) => u.id === e.user.id)
                ? { ...m, seen_by: [...(m.seen_by ?? []), e.user] }
                : m,
            ),
          },
      );
    } else if (e.type === "chat.updated") {
      setState((s) => s && { ...s, chat: { ...s.chat, ...e.chat } });
    }
  });

  async function toggleChatLike() {
    if (!state) return;
    const liked = !state.chat.liked_by_me;
    const r = await api<LikeStatus>(`/chats/${chatId}/like`, { method: liked ? "POST" : "DELETE" });
    setState(
      (s) =>
        s && {
          ...s,
          chat: { ...s.chat, likes: applyLike(s.chat.likes, r.count, me, r.liked_by_me), liked_by_me: r.liked_by_me },
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

  async function postComment(body: string, attachmentIds: number[]) {
    const m = await api<Message>(`/chats/${chatId}/messages`, { json: { body, attachment_ids: attachmentIds } });
    setState((s) => s && addMessage(s, m));
    refreshChats();
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  }

  async function postReply(body: string, attachmentIds: number[]) {
    if (!replyTarget) return;
    const m = await api<Message>(`/messages/${replyTarget.messageId}/replies`, {
      json: { body, reply_to_user_id: replyTarget.user.id, attachment_ids: attachmentIds },
    });
    setState((s) => s && addMessage(s, m));
    setReplyTarget(null);
    refreshChats();
  }

  async function setStatus(status: "open" | "closed") {
    try {
      await api(`/admin/chats/${chatId}`, { method: "PATCH", json: { status } });
    } catch (e) {
      report(e);
    }
  }

  if (denied) return <NotAllowed message={denied} />;
  if (error) return <p className="p-6 text-destructive">{error}</p>;
  if (!state) return <p className="p-6 text-muted-foreground">Loading…</p>;

  const { chat } = state;
  const closed = chat.status === "closed";

  // A message and its replies. A reply to a message on the last level goes next to it, under the same parent.
  function renderMessage(m: Message, depth: number, parentId: number | null): ReactNode {
    const replies = m.replies ?? [];
    const canNest = depth < MAX_DEPTH;
    const composerHere = canNest && !closed && replyTarget?.parentId === m.id;
    return (
      <div key={m.id} className="space-y-2">
        <MessageBubble
          message={m}
          small={depth > 1}
          closed={closed}
          messageIds={messageIds}
          onLike={() => toggleMessageLike(m).catch(report)}
          onReply={() => setReplyTarget({ parentId: canNest ? m.id : parentId!, messageId: m.id, user: m.author })}
        />
        {canNest && (replies.length > 0 || composerHere) && (
          <div className={`${depth === 1 ? "ml-11" : "ml-9"} space-y-2 border-l pl-3`}>
            {replies.map((r) => renderMessage(r, depth + 1, m.id))}
            {composerHere && replyTarget && (
              <Composer
                key={`${replyTarget.messageId}-${replyTarget.user.id}`}
                chatId={chatId}
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
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-6">
      <article className="rounded-xl border bg-card">
        <header className="flex items-start gap-3 p-4 pb-2">
          <Avatar user={chat.author} size={42} />
          <div className="min-w-0 flex-1">
            <div className="font-semibold">{chat.author.display_name}</div>
            <div className="text-xs text-muted-foreground">
              <Link href={`/groups/${chat.group.id}`} className="hover:underline">
                {chat.group.name}
              </Link>{" "}
              · {timeAgo(chat.created_at)} · chat #{chat.id}
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
          <h1 className="text-xl font-semibold">{chat.title}</h1>
          <AutomationBadges chat={chat} />
          {chat.body && (
            <Markdown messageIds={messageIds} mentions={chat.mentions}>
              {chat.body}
            </Markdown>
          )}
          <Attachments items={chat.attachments ?? []} />
        </div>
        <div className="flex items-center gap-2 border-t px-2 py-1">
          <LikeButton
            size="md"
            likes={chat.likes}
            liked={chat.liked_by_me}
            disabled={closed}
            onToggle={() => toggleChatLike().catch(report)}
          />
          <span className="ml-auto pr-2 text-xs text-muted-foreground">
            {countMessages(state.messages)} comments
          </span>
          {me.is_admin && (
            <>
              <Link href={`/admin/chats/${chat.id}`} className={buttonVariants({ variant: "ghost", size: "sm" })}>
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
          <Lock className="size-4" /> This chat is closed. You can read it, but no new comments or likes.
        </div>
      )}

      <div className="space-y-4">
        {state.messages.map((c) => renderMessage(c, 1, null))}
        {state.messages.length === 0 && <p className="text-sm text-muted-foreground">No comments yet.</p>}
      </div>

      {!closed && (
        <div className="sticky bottom-0 border-t bg-background/95 py-3 backdrop-blur">
          <Composer chatId={chatId} me={me} placeholder="Write a comment…" onSend={postComment} />
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
