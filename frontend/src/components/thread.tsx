"use client";

import { useState } from "react";
import { SendHorizontal, ThumbsUp, X } from "lucide-react";
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
      title={who ? `Liked by ${who}` : "Like"}
      className={cn(
        "inline-flex items-center gap-1 font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60",
        size === "sm" ? "text-xs" : "rounded-md px-3 py-1.5 text-sm hover:bg-muted",
        liked ? "text-primary" : "text-muted-foreground hover:text-foreground",
      )}
    >
      <ThumbsUp className={cn(size === "sm" ? "size-3" : "size-4", liked && "fill-current")} />
      Like{likes.count > 0 && <span className="font-normal">· {likes.count}</span>}
    </button>
  );
}

export function Composer({
  placeholder,
  onSend,
  replyTo,
  onCancelReply,
  autoFocus,
  me,
}: {
  placeholder: string;
  onSend: (body: string) => Promise<void>;
  replyTo?: UserRef | null;
  onCancelReply?: () => void;
  autoFocus?: boolean;
  me: UserRef;
}) {
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send() {
    if (!body.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      await onSend(body);
      setBody("");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-start gap-2">
      <Avatar user={me} size={32} />
      <div className="flex-1 space-y-1">
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
        <div className="flex items-end gap-2 rounded-2xl bg-muted px-3 py-1.5">
          <Textarea
            value={body}
            autoFocus={autoFocus}
            onChange={(e) => setBody(e.target.value)}
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
          <Button size="icon-sm" variant="ghost" onClick={send} disabled={busy || !body.trim()} title="Send (Enter)">
            <SendHorizontal className="size-4" />
          </Button>
        </div>
        <div className="px-2 text-[11px] text-muted-foreground">
          Enter to send · Shift+Enter for a new line · Markdown supported
        </div>
        {error && <p className="px-2 text-xs text-destructive">{error}</p>}
      </div>
    </div>
  );
}

export function MessageBubble({
  message,
  small,
  closed,
  onLike,
  onReply,
}: {
  message: Message;
  small?: boolean;
  closed: boolean;
  onLike: () => void;
  onReply: () => void;
}) {
  return (
    <div className="flex items-start gap-2" id={`m${message.id}`}>
      <Avatar user={message.author} size={small ? 28 : 36} />
      <div className="min-w-0 max-w-[85%]">
        <div className="rounded-2xl bg-muted px-3 py-2">
          <div className="text-sm font-semibold">{message.author.display_name}</div>
          <div className="inline-first text-sm">
            {message.reply_to && (
              <span className="mr-1 font-semibold text-primary">{message.reply_to.display_name}</span>
            )}
            <Markdown>{message.body}</Markdown>
          </div>
        </div>
        <div className="mt-0.5 flex items-center gap-3 px-3 text-xs text-muted-foreground">
          <span title={new Date(message.created_at).toLocaleString()}>{timeAgo(message.created_at)}</span>
          <LikeButton likes={message.likes} liked={message.liked_by_me} disabled={closed} onToggle={onLike} />
          {!closed && (
            <button type="button" onClick={onReply} className="font-semibold hover:text-foreground">
              Reply
            </button>
          )}
          <span className="opacity-50">#{message.id}</span>
        </div>
      </div>
    </div>
  );
}
