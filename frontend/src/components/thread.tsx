"use client";

import { useRef, useState } from "react";
import { Heart, Paperclip, SendHorizontal, X } from "lucide-react";
import { Attachments, UploadChips, useUploads } from "@/components/attachments";
import { Avatar } from "@/components/avatar";
import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import type { Likes, Message, UserRef } from "@/lib/types";
import { cn } from "@/lib/utils";

export function LikeButton({
  likes,
  liked,
  disabled,
  onToggle,
  size = "sm",
}: {
  likes: Likes;
  liked: boolean;
  disabled?: boolean;
  onToggle: () => void;
  size?: "sm" | "md";
}) {
  const who = likes.users.map((u) => u.display_name).join(", ");
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onToggle}
      title={who ? `Liked by ${who}` : undefined}
      aria-label={liked ? "Unlike" : "Like"}
      aria-pressed={liked}
      className={cn(
        "inline-flex items-center gap-1 font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60",
        size === "sm" ? "text-xs" : "rounded-md px-3 py-1.5 text-sm hover:bg-muted",
        liked ? "text-rose-500" : "text-muted-foreground hover:text-rose-400",
      )}
    >
      <Heart className={cn(size === "sm" ? "size-3.5" : "size-4", liked && "fill-current")} />
      {likes.count > 0 && <span className="font-normal">{likes.count}</span>}
    </button>
  );
}

export function Composer({
  workId,
  placeholder,
  onSend,
  replyTo,
  onCancelReply,
  autoFocus,
  me,
}: {
  workId: number;
  placeholder: string;
  onSend: (body: string, attachmentIds: number[]) => Promise<void>;
  replyTo?: UserRef | null;
  onCancelReply?: () => void;
  autoFocus?: boolean;
  me: UserRef;
}) {
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const uploads = useUploads(workId);
  const fileInput = useRef<HTMLInputElement>(null);
  const canSend = (body.trim() !== "" || uploads.ids.length > 0) && !uploads.busy && !busy;

  async function send() {
    if (!canSend) return;
    setBusy(true);
    setError(null);
    try {
      await onSend(body, uploads.ids);
      setBody("");
      uploads.clear();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="flex items-start gap-2"
      onDragOver={(e) => {
        if (!e.dataTransfer.types.includes("Files")) return;
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        if (!e.dataTransfer.files.length) return;
        e.preventDefault();
        setDragging(false);
        uploads.add(e.dataTransfer.files);
      }}
    >
      <Avatar user={me} size={32} />
      <div className="min-w-0 flex-1 space-y-1">
        {replyTo && (
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            Replying to <span className="font-semibold text-primary">{replyTo.display_name}</span>
            {onCancelReply && (
              <button type="button" onClick={onCancelReply} className="rounded p-0.5 hover:bg-muted" title="Cancel">
                <X className="size-3" />
              </button>
            )}
          </div>
        )}
        <div
          className={cn(
            "space-y-2 rounded-2xl bg-muted px-3 py-1.5",
            dragging && "ring-2 ring-primary ring-offset-2 ring-offset-background",
          )}
        >
          <UploadChips items={uploads.items} onRemove={uploads.remove} />
          <div className="flex items-end gap-1">
            <Textarea
              value={body}
              autoFocus={autoFocus}
              onChange={(e) => setBody(e.target.value)}
              onPaste={(e) => {
                const files = Array.from(e.clipboardData.files);
                if (files.length) {
                  e.preventDefault();
                  uploads.add(files);
                }
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              placeholder={placeholder}
              rows={1}
              className="max-h-48 min-h-0 resize-none border-0 bg-transparent p-1 shadow-none focus-visible:ring-0 dark:bg-transparent"
            />
            <input
              ref={fileInput}
              type="file"
              multiple
              hidden
              onChange={(e) => {
                if (e.target.files) uploads.add(e.target.files);
                e.target.value = "";
              }}
            />
            <Button size="icon-sm" variant="ghost" onClick={() => fileInput.current?.click()} title="Attach files">
              <Paperclip className="size-4" />
            </Button>
            <Button size="icon-sm" variant="ghost" onClick={send} disabled={!canSend} title="Send (Enter)">
              <SendHorizontal className="size-4" />
            </Button>
          </div>
        </div>
        <div className="px-2 text-[11px] text-muted-foreground">
          Enter to send · Shift+Enter for a new line · Markdown supported · Drop or paste files to attach
        </div>
        {error && <p className="px-2 text-xs text-destructive">{error}</p>}
      </div>
    </div>
  );
}

const SEEN_ICONS = 5;

/** Small avatars of the users who saw a message; the rest as +N. */
export function SeenBy({ users }: { users: UserRef[] }) {
  if (users.length === 0) return null;
  const names = users.map((u) => u.display_name).join(", ");
  const extra = users.length - SEEN_ICONS;
  return (
    <span className="ml-auto inline-flex items-center" title={`Seen by ${names}`} aria-label={`Seen by ${names}`}>
      {users.slice(0, SEEN_ICONS).map((u, i) => (
        <Avatar key={u.id} user={u} size={16} className={cn("rounded-full ring-2 ring-background", i > 0 && "-ml-1")} />
      ))}
      {extra > 0 && <span className="ml-1 text-[11px]">+{extra}</span>}
    </span>
  );
}

export function MessageBubble({
  message,
  small,
  closed,
  messageIds,
  onLike,
  onReply,
}: {
  message: Message;
  small?: boolean;
  closed: boolean;
  /** Ids of the messages in this work; `#id` in the text links to them. */
  messageIds?: Set<number>;
  onLike: () => void;
  onReply: () => void;
}) {
  return (
    <div className="flex scroll-mt-24 items-start gap-2" id={`m${message.id}`}>
      <Avatar user={message.author} size={small ? 28 : 36} />
      <div className="min-w-0 max-w-[85%]">
        <div className="rounded-2xl bg-muted px-3 py-2">
          <div className="flex flex-wrap items-baseline gap-x-1.5">
            <span className="text-sm font-semibold">{message.author.display_name}</span>
            <span className="text-[11px] text-muted-foreground">
              <span title={new Date(message.created_at).toLocaleString()}>{timeAgo(message.created_at)}</span>
              {" · "}#{message.id}
            </span>
          </div>
          <div className="inline-first text-sm">
            {message.reply_to && (
              <span className="mr-1 font-semibold text-primary">{message.reply_to.display_name}</span>
            )}
            {message.body && <Markdown messageIds={messageIds}>{message.body}</Markdown>}
          </div>
          <Attachments items={message.attachments ?? []} />
        </div>
        <div className="mt-0.5 flex items-center gap-3 px-3 text-xs text-muted-foreground">
          <LikeButton likes={message.likes} liked={message.liked_by_me} disabled={closed} onToggle={onLike} />
          {!closed && (
            <button type="button" onClick={onReply} className="font-semibold hover:text-foreground">
              Reply
            </button>
          )}
          <SeenBy users={message.seen_by ?? []} />
        </div>
      </div>
    </div>
  );
}
