"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Home,
  LogOut,
  Settings,
  Shield,
  Users,
  FolderKanban,
  MessagesSquare,
  ArrowLeft,
  LayoutDashboard,
} from "lucide-react";
import { Avatar } from "@/components/avatar";
import { usePanel } from "@/components/panel";
import { api } from "@/lib/api";
import { useAuth, useMe } from "@/lib/auth";
import { useLive, useLiveEvent } from "@/lib/live";
import { useWorks } from "@/lib/works";
import type { Person } from "@/lib/types";
import { cn } from "@/lib/utils";

function NavLink({
  href,
  icon: Icon,
  label,
  badge,
  exact,
}: {
  href: string;
  icon?: React.ComponentType<{ className?: string }>;
  label: string;
  badge?: number;
  exact?: boolean;
}) {
  const pathname = usePathname();
  const active = exact ? pathname === href : pathname === href || pathname.startsWith(href + "/");
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors hover:bg-muted",
        active && "bg-muted font-medium text-foreground",
        !active && "text-muted-foreground",
      )}
    >
      {Icon ? <Icon className="size-4 shrink-0" /> : <span className="size-4 shrink-0" />}
      <span className="flex-1 truncate">{label}</span>
      {!!badge && (
        <span className="rounded-full bg-primary px-1.5 text-xs font-semibold text-primary-foreground">{badge}</span>
      )}
    </Link>
  );
}

function LeftNav() {
  const me = useMe();
  const { logout } = useAuth();
  const { works } = useWorks();
  const { connected } = useLive();
  const pathname = usePathname();
  const inAdmin = pathname.startsWith("/admin");

  const unreadByGroup = new Map<number, number>();
  for (const w of works ?? []) unreadByGroup.set(w.group_id, (unreadByGroup.get(w.group_id) ?? 0) + w.unread_count);
  const totalUnread = (works ?? []).filter((w) => w.joined).reduce((n, w) => n + w.unread_count, 0);

  return (
    <nav className="flex h-full flex-col gap-1 p-3">
      <Link href="/" className="mb-3 flex items-center gap-2 px-3 py-1 text-lg font-bold">
        <MessagesSquare className="size-5 text-primary" /> AIChat
      </Link>
      {inAdmin ? (
        <>
          <NavLink href="/admin" icon={LayoutDashboard} label="Dashboard" exact />
          <NavLink href="/admin/users" icon={Users} label="Users" />
          <NavLink href="/admin/groups" icon={Shield} label="Groups" />
          <NavLink href="/admin/works" icon={FolderKanban} label="Works" />
          <div className="my-2 border-t" />
          <NavLink href="/" icon={ArrowLeft} label="Back to site" exact />
        </>
      ) : (
        <>
          <NavLink href="/" icon={Home} label="Home" badge={totalUnread} exact />
          <div className="mt-4 mb-1 px-3 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            My groups
          </div>
          {me.groups.length === 0 && (
            <p className="px-3 text-xs text-muted-foreground">You are not in any group yet.</p>
          )}
          {me.groups.map((g) => (
            <NavLink key={g.id} href={`/groups/${g.id}`} label={g.name} badge={unreadByGroup.get(g.id)} />
          ))}
          <div className="my-2 border-t" />
          <NavLink href="/settings" icon={Settings} label="Settings" />
          {me.is_admin && <NavLink href="/admin" icon={Shield} label="Admin" />}
        </>
      )}
      <div className="mt-auto flex items-center gap-2 rounded-lg border p-2">
        <Avatar user={me} size={32} online={connected} />
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium">{me.display_name}</div>
          <div className="truncate text-xs text-muted-foreground">
            @{me.username} · {connected ? "live" : "reconnecting…"}
          </div>
        </div>
        <button onClick={logout} title="Log out" className="rounded p-1 text-muted-foreground hover:bg-muted">
          <LogOut className="size-4" />
        </button>
      </div>
    </nav>
  );
}

function RightPanel() {
  const { groupId } = usePanel();
  const { online } = useLive();
  const me = useMe();
  const [people, setPeople] = useState<Person[]>([]);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const path = groupId ? `/groups/${groupId}/members` : "/people";
    api<Person[]>(path)
      .then((p) => !cancelled && setPeople(p))
      .catch(() => !cancelled && setPeople([]));
    return () => {
      cancelled = true;
    };
  }, [groupId, reload, me.groups]);
  const group = me.groups.find((g) => g.id === groupId);
  const title = groupId ? `Members · ${group?.name ?? "group"}` : "People";

  useLiveEvent((e) => {
    if (e.type === "groups.changed" || e.type === "access.revoked" || e.type === "group.deleted")
      setReload((n) => n + 1);
  });

  const sorted = [...people].sort((a, b) => Number(online.has(b.id)) - Number(online.has(a.id)));
  return (
    <aside className="flex h-full flex-col p-3">
      <div className="mb-2 px-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">{title}</div>
      <ul className="space-y-1 overflow-y-auto">
        {sorted.map((p) => (
          <li key={p.id} className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-muted">
            <Avatar user={p} size={30} online={online.has(p.id)} />
            <div className="min-w-0">
              <div className="truncate text-sm">{p.display_name}</div>
              <div className="truncate text-xs text-muted-foreground">@{p.username}</div>
            </div>
          </li>
        ))}
        {sorted.length === 0 && <li className="px-2 text-xs text-muted-foreground">No one here yet.</li>}
      </ul>
    </aside>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto grid h-screen w-full max-w-[1400px] grid-cols-1 md:grid-cols-[240px_1fr] lg:grid-cols-[240px_1fr_260px]">
      <div className="hidden border-r bg-card/40 md:block">
        <LeftNav />
      </div>
      <main className="min-w-0 overflow-y-auto">{children}</main>
      <div className="hidden border-l bg-card/40 lg:block">
        <RightPanel />
      </div>
    </div>
  );
}
