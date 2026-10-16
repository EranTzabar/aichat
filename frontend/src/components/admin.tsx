"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { buttonVariants } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";

export function PageHeader({
  title,
  description,
  action,
  back,
}: {
  title: string;
  description?: string;
  action?: { href: string; label: string };
  back?: { href: string; label: string };
}) {
  return (
    <div className="space-y-1">
      {back && (
        <Link href={back.href} className="text-sm text-muted-foreground hover:underline">
          ← {back.label}
        </Link>
      )}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">{title}</h1>
          {description && <p className="text-sm text-muted-foreground">{description}</p>}
        </div>
        {action && (
          <Link href={action.href} className={buttonVariants()}>
            {action.label}
          </Link>
        )}
      </div>
    </div>
  );
}

export function Tabs({ tabs }: { tabs: { href: string; label: string }[] }) {
  const pathname = usePathname();
  return (
    <div className="flex gap-1 border-b">
      {tabs.map((t) => (
        <Link
          key={t.href}
          href={t.href}
          className={cn(
            "-mb-px border-b-2 px-3 py-2 text-sm",
            pathname === t.href
              ? "border-primary font-medium"
              : "border-transparent text-muted-foreground hover:text-foreground",
          )}
        >
          {t.label}
        </Link>
      ))}
    </div>
  );
}

/** Fetch JSON for a page; `reload` refetches. */
export function useFetch<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(() => {
    if (!path) return;
    api<T>(path)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(errorMessage(e)));
  }, [path]);
  useEffect(reload, [reload]);
  return { data, error, reload, setData };
}

export function Status({ msg }: { msg: { ok: boolean; text: string } | null }) {
  if (!msg) return null;
  return <p className={msg.ok ? "text-sm text-green-500" : "text-sm text-destructive"}>{msg.text}</p>;
}
