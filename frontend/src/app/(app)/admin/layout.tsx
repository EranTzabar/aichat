"use client";

import { NotAllowed } from "@/components/not-allowed";
import { useMe } from "@/lib/auth";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const me = useMe();
  if (!me.is_admin) return <NotAllowed message="Only the admin can open the management pages." />;
  return <div className="mx-auto max-w-4xl space-y-6 p-6">{children}</div>;
}
