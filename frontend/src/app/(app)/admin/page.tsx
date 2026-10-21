"use client";

import Link from "next/link";
import { FolderKanban, ScrollText, Shield, Users } from "lucide-react";
import { PageHeader, useFetch } from "@/components/admin";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { AdminUser, Group } from "@/lib/types";
import { useChats } from "@/lib/chats";

export default function AdminDashboard() {
  const users = useFetch<AdminUser[]>("/admin/users");
  const groups = useFetch<Group[]>("/admin/groups");
  const { chats } = useChats();

  const cards = [
    {
      href: "/admin/users",
      icon: Users,
      title: "Users",
      count: users.data?.length,
      text: "Create users, edit settings, groups and API tokens.",
    },
    {
      href: "/admin/groups",
      icon: Shield,
      title: "Groups",
      count: groups.data?.length,
      text: "Create groups and see their members.",
    },
    {
      href: "/admin/chats",
      icon: FolderKanban,
      title: "Chats",
      count: chats?.length,
      text: "Start chats (tag people, repeat, close automatically), edit or close chats.",
    },
    {
      href: "/admin/audit",
      icon: ScrollText,
      title: "Audit log",
      count: undefined,
      text: "Who changed what, from the website or an AI.",
    },
  ];
  return (
    <>
      <PageHeader title="Admin" description="Manage users, groups and chats, and see the audit log." />
      <div className="grid gap-4 sm:grid-cols-2">
        {cards.map((c) => (
          <Link key={c.href} href={c.href}>
            <Card className="h-full transition-colors hover:bg-muted/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <c.icon className="size-4 text-primary" /> {c.title}
                  {c.href !== "/admin/audit" && <span className="ml-auto text-2xl">{c.count ?? "…"}</span>}
                </CardTitle>
                <CardDescription>{c.text}</CardDescription>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </>
  );
}
