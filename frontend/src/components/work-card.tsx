import Link from "next/link";
import { Lock } from "lucide-react";
import { Avatar } from "@/components/avatar";
import { Badge } from "@/components/ui/badge";
import { timeAgo } from "@/lib/format";
import type { WorkListItem } from "@/lib/types";
import { cn } from "@/lib/utils";

export function WorkCard({ work }: { work: WorkListItem }) {
  const lm = work.last_message;
  return (
    <Link
      href={`/works/${work.id}`}
      className={cn(
        "flex items-center gap-3 rounded-xl border bg-card p-3 transition-colors hover:bg-muted/60",
        work.unread_count > 0 && "border-primary/50",
      )}
    >
      {lm ? (
        <Avatar user={lm.author} size={44} />
      ) : (
        <div className="flex size-11 shrink-0 items-center justify-center rounded-full bg-primary/15 text-lg font-semibold text-primary">
          {work.title[0]?.toUpperCase()}
        </div>
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className={cn("truncate", work.unread_count > 0 ? "font-semibold" : "font-medium")}>{work.title}</span>
          {work.status === "closed" && (
            <Badge variant="secondary" className="gap-1">
              <Lock className="size-3" /> closed
            </Badge>
          )}
        </div>
        <div className="truncate text-sm text-muted-foreground">
          {lm ? (
            <>
              <span className="text-foreground/80">{lm.author.display_name}:</span> {lm.body_preview}
            </>
          ) : (
            "No messages yet. Be the first to write!"
          )}
        </div>
        <div className="text-xs text-muted-foreground">
          {work.group_name} · {timeAgo(work.last_activity_at)} · {work.message_count} messages
        </div>
      </div>
      {work.unread_count > 0 && (
        <span className="rounded-full bg-primary px-2 py-0.5 text-xs font-semibold text-primary-foreground">
          {work.unread_count}
        </span>
      )}
    </Link>
  );
}

export function WorkSection({ title, works, empty }: { title: string; works: WorkListItem[]; empty: string }) {
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-semibold tracking-wide text-muted-foreground uppercase">
        {title} <span className="font-normal">({works.length})</span>
      </h2>
      {works.length === 0 ? (
        <p className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">{empty}</p>
      ) : (
        <div className="space-y-2">
          {works.map((w) => (
            <WorkCard key={w.id} work={w} />
          ))}
        </div>
      )}
    </section>
  );
}
