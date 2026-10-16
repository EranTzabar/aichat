"use client";

import Link from "next/link";
import { FolderKanban, Shield, Users } from "lucide-react";
import { PageHeader, useFetch } from "@/components/admin";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { AdminUser, Group } from "@/lib/types";
import { useWorks } from "@/lib/works";

export default function AdminDashboard() {
  const users = useFetch<AdminUser[]>("/admin/users");
  const groups = useFetch<Group[]>("/admin/groups");
  const { works } = useWorks();

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
      href: "/admin/works",
      icon: FolderKanban,
      title: "Works",
      count: works?.length,
      text: "Start a new work in a group, edit or close works.",
    },
  ];
  return (
    <>
      <PageHeader title="Admin" description="Manage users, groups and works." />
      <div className="grid gap-4 sm:grid-cols-3">
        {cards.map((c) => (
          <Link key={c.href} href={c.href}>
            <Card className="h-full transition-colors hover:bg-muted/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <c.icon className="size-4 text-primary" /> {c.title}
                  <span className="ml-auto text-2xl">{c.count ?? "…"}</span>
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
