"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { Status, useFetch } from "@/components/admin";
import { AvatarUpload } from "@/components/avatar-upload";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { dateTime } from "@/lib/format";
import type { AdminUser } from "@/lib/types";

export default function UserSettingsPage() {
  const { id } = useParams<{ id: string }>();
  const { user: me, refreshMe } = useAuth();
  const { data: user, error, setData } = useFetch<AdminUser>(`/admin/users/${id}`);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function patch(body: Record<string, unknown>, okText: string) {
    setMsg(null);
    try {
      const updated = await api<AdminUser>(`/admin/users/${id}`, { method: "PATCH", json: body });
      setData(updated);
      setMsg({ ok: true, text: okText });
      if (updated.id === me?.id) refreshMe();
    } catch (e) {
      setMsg({ ok: false, text: errorMessage(e) });
    }
  }

  if (error) return <p className="text-destructive">{error}</p>;
  if (!user) return <p className="text-muted-foreground">Loading…</p>;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>
            {user.display_name} <span className="font-normal text-muted-foreground">@{user.username}</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <AvatarUpload user={user} endpoint={`/admin/users/${user.id}/avatar`} />
          <ProfileForm key={user.id} user={user} patch={patch} />
          <Status msg={msg} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Account status</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <Label className="flex items-center gap-3 font-normal">
            <Switch
              checked={user.is_active}
              disabled={user.id === me?.id}
              onCheckedChange={(v) => patch({ is_active: v }, v ? "User enabled." : "User disabled.")}
            />
            Active{" "}
            {user.id === me?.id && (
              <span className="text-xs text-muted-foreground">(you can&apos;t disable yourself)</span>
            )}
          </Label>
          <div className="grid grid-cols-[140px_1fr] gap-y-1">
            <span className="text-muted-foreground">Role</span>
            <span>{user.is_admin ? "Admin" : "User"}</span>
            <span className="text-muted-foreground">Created</span>
            <span>{dateTime(user.created_at)}</span>
            <span className="text-muted-foreground">Last login</span>
            <span>{dateTime(user.last_login_at)}</span>
            <span className="text-muted-foreground">Last API use</span>
            <span>{dateTime(user.last_api_use_at)}</span>
            <span className="text-muted-foreground">API access</span>
            <span>{user.api_enabled ? "enabled" : "disabled"}</span>
            <span className="text-muted-foreground">Groups</span>
            <span>{user.groups.map((g) => g.name).join(", ") || "none"}</span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function ProfileForm({
  user,
  patch,
}: {
  user: AdminUser;
  patch: (body: Record<string, unknown>, okText: string) => Promise<void>;
}) {
  const [form, setForm] = useState({ display_name: user.display_name, bio: user.bio, password: "" });
  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        const body: Record<string, unknown> = { display_name: form.display_name, bio: form.bio };
        if (form.password) body.password = form.password;
        patch(body, form.password ? "Saved. Password was reset." : "Saved.");
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="dn">Display name</Label>
          <Input
            id="dn"
            value={form.display_name}
            onChange={(e) => setForm({ ...form, display_name: e.target.value })}
            required
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="pw">Reset password</Label>
          <Input
            id="pw"
            value={form.password}
            placeholder="Leave empty to keep"
            minLength={6}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="bio">Bio</Label>
        <Textarea id="bio" value={form.bio} onChange={(e) => setForm({ ...form, bio: e.target.value })} />
      </div>
      <Button type="submit">Save</Button>
    </form>
  );
}
