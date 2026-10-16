"use client";

import { useParams } from "next/navigation";
import { PageHeader, Tabs } from "@/components/admin";

export default function UserLayout({ children }: { children: React.ReactNode }) {
  const { id } = useParams<{ id: string }>();
  const base = `/admin/users/${id}`;
  return (
    <>
      <PageHeader title="User" back={{ href: "/admin/users", label: "Users" }} />
      <Tabs
        tabs={[
          { href: base, label: "Settings" },
          { href: `${base}/permissions`, label: "Permissions" },
          { href: `${base}/token`, label: "API token" },
        ]}
      />
      {children}
    </>
  );
}
