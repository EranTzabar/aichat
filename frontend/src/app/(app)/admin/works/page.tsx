"use client";

import Link from "next/link";
import { PageHeader } from "@/components/admin";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { timeAgo } from "@/lib/format";
import { useWorks } from "@/lib/works";

export default function AdminWorksPage() {
  const { works, error } = useWorks();
  return (
    <>
      <PageHeader
        title="Works"
        description="Every work in every group."
        action={{ href: "/admin/works/new", label: "New work" }}
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
            {works?.map((w) => (
              <TableRow key={w.id}>
                <TableCell>
                  <Link href={`/works/${w.id}`} className="font-medium hover:underline">
                    {w.title}
                  </Link>
                </TableCell>
                <TableCell className="text-sm">{w.group_name}</TableCell>
                <TableCell>
                  <Badge variant={w.status === "open" ? "outline" : "secondary"}>{w.status}</Badge>
                </TableCell>
                <TableCell className="text-right">{w.message_count}</TableCell>
                <TableCell className="text-xs text-muted-foreground">{timeAgo(w.last_activity_at)}</TableCell>
                <TableCell className="text-right">
                  <Link href={`/admin/works/${w.id}`} className={buttonVariants({ variant: "ghost", size: "sm" })}>
                    Edit
                  </Link>
                </TableCell>
              </TableRow>
            ))}
            {works?.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-muted-foreground">
                  No works yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </>
  );
}
