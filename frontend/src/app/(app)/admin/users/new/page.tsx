"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { PageHeader } from "@/components/admin";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, avatarProblem, errorMessage } from "@/lib/api";
import type { AdminUser } from "@/lib/types";

export default function NewUserPage() {
  const router = useRouter();
  const [form, setForm] = useState({ username: "", display_name: "", password: "", bio: "", is_admin: false });
  const [icon, setIcon] = useState<File | null>(null);
  // Set once the user exists, so a retry only uploads the icon instead of creating the user again.
  const [created, setCreated] = useState<AdminUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const done = (user: AdminUser) => router.push(`/admin/users/${user.id}/permissions`);

  function pickIcon(file: File | null) {
    setIcon(file);
    setError(file ? avatarProblem(file) : null);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const problem = icon && avatarProblem(icon);
    if (problem) {
      setError(problem);
      return;
    }
    setBusy(true);
    setError(null);
    let user = created;
    try {
      if (!user) {
        user = await api<AdminUser>("/admin/users", { json: form });
        setCreated(user);
      }
      if (icon) {
        const data = new FormData();
        data.append("file", icon);
        await api(`/admin/users/${user.id}/avatar`, { form: data });
      }
      done(user);
    } catch (err) {
      setError(
        user
          ? `User "${user.username}" was created, but the icon was not saved: ${errorMessage(err)} ` +
              "Choose another image and press Save again, or continue without an icon."
          : errorMessage(err),
      );
      setBusy(false);
    }
  }

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm({ ...form, [k]: e.target.value });

  return (
    <>
      <PageHeader title="New user" back={{ href: "/admin/users", label: "Users" }} />
      <Card>
        <CardContent>
          <form onSubmit={submit} className="space-y-4">
            <fieldset disabled={!!created} className="space-y-4 disabled:opacity-70">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="username">Username</Label>
                  <Input
                    id="username"
                    value={form.username}
                    onChange={set("username")}
                    required
                    pattern="[A-Za-z0-9_.\-]+"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="display_name">Display name</Label>
                  <Input id="display_name" value={form.display_name} onChange={set("display_name")} required />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="password">Initial password</Label>
                  <Input
                    id="password"
                    type="text"
                    value={form.password}
                    onChange={set("password")}
                    required
                    minLength={6}
                  />
                </div>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="bio">Bio</Label>
                <Textarea id="bio" value={form.bio} onChange={set("bio")} />
              </div>
              <Label className="flex items-center gap-2 font-normal">
                <Checkbox checked={form.is_admin} onCheckedChange={(v) => setForm({ ...form, is_admin: !!v })} />
                Admin (can manage everything)
              </Label>
            </fieldset>
            <div className="space-y-1.5 sm:max-w-[calc(50%-0.5rem)]">
              <Label htmlFor="icon">Icon (optional, up to 2 MB)</Label>
              <Input
                id="icon"
                type="file"
                accept="image/png,image/jpeg,image/gif,image/webp"
                onChange={(e) => pickIcon(e.target.files?.[0] ?? null)}
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="flex gap-2">
              <Button type="submit" disabled={busy}>
                {busy ? "Saving…" : created ? "Save icon" : "Create user"}
              </Button>
              {created && (
                <Button type="button" variant="outline" onClick={() => done(created)}>
                  Continue without icon
                </Button>
              )}
            </div>
          </form>
        </CardContent>
      </Card>
    </>
  );
}
