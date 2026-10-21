"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Status, useFetch } from "@/components/admin";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AdminUser, Group } from "@/lib/types";

export default function PermissionsPage() {
  const { id } = useParams<{ id: string }>();
  const { user: me, refreshMe } = useAuth();
  const { data: user, setData } = useFetch<AdminUser>(`/admin/users/${id}`);
  const { data: groups } = useFetch<Group[]>("/admin/groups");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function saveGroups(selected: Set<number>) {
    setMsg(null);
    try {
      const updated = await api<AdminUser>(`/admin/users/${id}/groups`, {
        method: "PUT",
        json: { group_ids: [...selected] },
      });
      setData(updated);
      setMsg({ ok: true, text: "Groups saved." });
      if (updated.id === me?.id) refreshMe();
    } catch (e) {
      setMsg({ ok: false, text: errorMessage(e) });
    }
  }

  async function setApi(enabled: boolean) {
    try {
      setData(await api<AdminUser>(`/admin/users/${id}`, { method: "PATCH", json: { api_enabled: enabled } }));
    } catch (e) {
      setMsg({ ok: false, text: errorMessage(e) });
    }
  }

  if (!user || !groups) return <p className="text-muted-foreground">Loading…</p>;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Groups</CardTitle>
          <CardDescription>
            {user.display_name} can read and write in the chats of these groups. A user can be in several groups.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {groups.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No groups exist yet.{" "}
              <Link href="/admin/groups/new" className="text-primary underline">
                Create a group first
              </Link>
              .
            </p>
          ) : (
            <GroupPicker key={user.groups.map((g) => g.id).join(",")} user={user} groups={groups} onSave={saveGroups} />
          )}
          <Status msg={msg} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>API access</CardTitle>
          <CardDescription>
            When on, the user&apos;s API token works and acts exactly as this user (same groups and permissions).
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Label className="flex items-center gap-3 font-normal">
            <Switch checked={user.api_enabled} onCheckedChange={(v) => setApi(v)} />
            API enabled
          </Label>
        </CardContent>
      </Card>
    </div>
  );
}

function GroupPicker({
  user,
  groups,
  onSave,
}: {
  user: AdminUser;
  groups: Group[];
  onSave: (selected: Set<number>) => Promise<void>;
}) {
  const [selected, setSelected] = useState(() => new Set(user.groups.map((g) => g.id)));
  return (
    <>
      <div className="grid gap-2 sm:grid-cols-2">
        {groups.map((g) => (
          <Label key={g.id} className="flex items-center gap-2 rounded-lg border p-3 font-normal">
            <Checkbox
              checked={selected.has(g.id)}
              onCheckedChange={(v) => {
                const next = new Set(selected);
                if (v) next.add(g.id);
                else next.delete(g.id);
                setSelected(next);
              }}
            />
            <span className="flex-1">{g.name}</span>
            <span className="text-xs text-muted-foreground">{g.member_count} members</span>
          </Label>
        ))}
      </div>
      <Button onClick={() => onSave(selected)}>Save groups</Button>
    </>
  );
}
