"use client";

import Link from "next/link";
import { CalendarClock, Repeat } from "lucide-react";
import { PageHeader } from "@/components/admin";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { repeatText } from "@/components/chat-automation";
import { dateTime, timeAgo } from "@/lib/format";
import { useChats } from "@/lib/chats";

export default function AdminChatsPage() {
  const { chats, error } = useChats();
  return (
    <>
      <PageHeader
        title="Chats"
        description="Every chat in every group."
        action={{ href: "/admin/chats/new", label: "New chat" }}
      />
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="rounded-xl border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Title</TableHead>
              <TableHead>Group</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Messages</TableHead>
              <TableHead>Last activity</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {chats?.map((w) => (
              <TableRow key={w.id}>
                <TableCell>
                  <Link href={`/chats/${w.id}`} className="font-medium hover:underline">
                    {w.title}
                  </Link>
                  {(w.repeat || (w.close_at && w.status === "open")) && (
                    <div className="flex flex-wrap gap-x-3 text-xs text-muted-foreground">
                      {w.repeat && (
                        <span className="inline-flex items-center gap-1">
                          <Repeat className="size-3" /> {repeatText(w.repeat)}
                          {w.next_copy_at && ` · next ${dateTime(w.next_copy_at)}`}
                        </span>
                      )}
                      {w.close_at && w.status === "open" && (
                        <span className="inline-flex items-center gap-1">
                          <CalendarClock className="size-3" /> closes {dateTime(w.close_at)}
                        </span>
                      )}
                    </div>
                  )}
                </TableCell>
                <TableCell className="text-sm">{w.group_name}</TableCell>
                <TableCell>
                  <Badge variant={w.status === "open" ? "outline" : "secondary"}>{w.status}</Badge>
                </TableCell>
                <TableCell className="text-right">{w.message_count}</TableCell>
                <TableCell className="text-xs text-muted-foreground">{timeAgo(w.last_activity_at)}</TableCell>
                <TableCell className="text-right">
                  <Link href={`/admin/chats/${w.id}`} className={buttonVariants({ variant: "ghost", size: "sm" })}>
                    Edit
                  </Link>
                </TableCell>
              </TableRow>
            ))}
            {chats?.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-muted-foreground">
                  No chats yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </>
  );
}
