"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { PanelProvider } from "@/components/panel";
import { Shell } from "@/components/shell";
import { useAuth } from "@/lib/auth";
import { LiveProvider } from "@/lib/live";
import { WorksProvider } from "@/lib/works";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, token, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user || !token) {
    return <div className="flex flex-1 items-center justify-center text-muted-foreground">Loading…</div>;
  }
  return (
    <LiveProvider token={token}>
      <WorksProvider>
        <PanelProvider>
          <Shell>{children}</Shell>
        </PanelProvider>
      </WorksProvider>
    </LiveProvider>
  );
}
