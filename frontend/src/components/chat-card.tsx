import Link from "next/link";
import { Lock } from "lucide-react";
import { Avatar } from "@/components/avatar";
import { MentionText } from "@/components/mention";
import { Badge } from "@/components/ui/badge";
import { timeAgo } from "@/lib/format";
import type { ChatListItem } from "@/lib/types";
import { cn } from "@/lib/utils";

export function ChatCard({ chat }: { chat: ChatListItem }) {
  const lm = chat.last_message;
  return (
    <Link
      href={`/chats/${chat.id}`}
      className={cn(
        "flex items-center gap-3 rounded-xl border bg-card p-3 transition-colors hover:bg-muted/60",
        chat.unread_count > 0 && "border-primary/50",
      )}
    >
      {lm ? (
        <Avatar user={lm.author} size={44} />
      ) : (
        <div className="flex size-11 shrink-0 items-center justify-center rounded-full bg-primary/15 text-lg font-semibold text-primary">
          {chat.title[0]?.toUpperCase()}
        </div>
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className={cn("truncate", chat.unread_count > 0 ? "font-semibold" : "font-medium")}>{chat.title}</span>
          {chat.status === "closed" && (
            <Badge variant="secondary" className="gap-1">
              <Lock className="size-3" /> closed
            </Badge>
          )}
        </div>
        <div className="truncate text-sm text-muted-foreground">
          {lm ? (
            <>
              <span className="text-foreground/80">{lm.author.display_name}:</span> <MentionText text={lm.body_preview} />
            </>
          ) : (
            "No messages yet. Be the first to write!"
          )}
        </div>
        <div className="text-xs text-muted-foreground">
          {chat.group_name} · {timeAgo(chat.last_activity_at)} · {chat.message_count} messages
        </div>
      </div>
      {chat.unread_mentions > 0 && (
        <span
          className="rounded-full bg-blue-600 px-2 py-0.5 text-xs font-semibold whitespace-nowrap text-white dark:bg-blue-500"
          title={`${chat.unread_mentions} unread message(s) tag you`}
        >
          @ You
        </span>
      )}
      {chat.unread_count > 0 && (
        <span className="rounded-full bg-primary px-2 py-0.5 text-xs font-semibold text-primary-foreground">
          {chat.unread_count}
        </span>
      )}
    </Link>
  );
}

export function ChatSection({ title, chats, empty }: { title: string; chats: ChatListItem[]; empty: string }) {
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-semibold tracking-wide text-muted-foreground uppercase">
        {title} <span className="font-normal">({chats.length})</span>
      </h2>
      {chats.length === 0 ? (
        <p className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">{empty}</p>
      ) : (
        <div className="space-y-2">
          {chats.map((w) => (
            <ChatCard key={w.id} chat={w} />
          ))}
        </div>
      )}
    </section>
  );
}
