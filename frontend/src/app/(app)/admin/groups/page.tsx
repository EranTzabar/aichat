"use client";

import Link from "next/link";
import { PageHeader, useFetch } from "@/components/admin";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Group } from "@/lib/types";

export default function GroupsPage() {
  const { data: groups, error } = useFetch<Group[]>("/admin/groups");
  return (
    <>
      <PageHeader
        title="Groups"
        description="Add users to groups from each user's Permissions page."
        action={{ href: "/admin/groups/new", label: "New group" }}
      />
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="rounded-xl border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Description</TableHead>
              <TableHead className="text-right">Members</TableHead>
              <TableHead className="text-right">Chats</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {groups?.map((g) => (
              <TableRow key={g.id}>
                <TableCell>
                  <Link href={`/admin/groups/${g.id}`} className="font-medium hover:underline">
                    {g.name}
                  </Link>
                </TableCell>
                <TableCell className="max-w-xs truncate text-sm text-muted-foreground">
                  {g.description || "—"}
                </TableCell>
                <TableCell className="text-right">{g.member_count}</TableCell>
                <TableCell className="text-right">{g.chat_count}</TableCell>
              </TableRow>
            ))}
            {groups?.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-muted-foreground">
                  No groups yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </>
  );
}
