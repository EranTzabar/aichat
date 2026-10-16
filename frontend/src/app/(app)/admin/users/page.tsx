"use client";

import Link from "next/link";
import { PageHeader, useFetch } from "@/components/admin";
import { Avatar } from "@/components/avatar";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { dateTime } from "@/lib/format";
import type { AdminUser } from "@/lib/types";

export default function UsersPage() {
  const { data: users, error } = useFetch<AdminUser[]>("/admin/users");
  return (
    <>
      <PageHeader
        title="Users"
        description="Only the admin can create users."
        action={{ href: "/admin/users/new", label: "New user" }}
      />
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="rounded-xl border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>User</TableHead>
              <TableHead>Groups</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Last login</TableHead>
              <TableHead>Last API use</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users?.map((u) => (
              <TableRow key={u.id}>
                <TableCell>
                  <Link href={`/admin/users/${u.id}`} className="flex items-center gap-2 hover:underline">
                    <Avatar user={u} size={28} />
                    <span>
                      <span className="font-medium">{u.display_name}</span>{" "}
                      <span className="text-muted-foreground">@{u.username}</span>
                    </span>
                    {u.is_admin && <Badge>admin</Badge>}
                  </Link>
                </TableCell>
                <TableCell className="text-sm">{u.groups.map((g) => g.name).join(", ") || "—"}</TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    <Badge variant={u.is_active ? "outline" : "destructive"}>
                      {u.is_active ? "active" : "disabled"}
                    </Badge>
                    {!u.api_enabled && <Badge variant="secondary">API off</Badge>}
                  </div>
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">{dateTime(u.last_login_at)}</TableCell>
                <TableCell className="text-xs text-muted-foreground">{dateTime(u.last_api_use_at)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </>
  );
}
