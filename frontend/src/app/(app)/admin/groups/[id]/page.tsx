"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { PageHeader, Status, useFetch } from "@/components/admin";
import { Avatar } from "@/components/avatar";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage } from "@/lib/api";
import type { GroupDetail } from "@/lib/types";

export default function GroupDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: group, error, setData } = useFetch<GroupDetail>(`/admin/groups/${id}`);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [confirm, setConfirm] = useState(false);

  async function save(form: { name: string; description: string }) {
    try {
      setData(await api<GroupDetail>(`/admin/groups/${id}`, { method: "PATCH", json: form }));
      setMsg({ ok: true, text: "Saved." });
    } catch (err) {
      setMsg({ ok: false, text: errorMessage(err) });
    }
  }

  async function remove() {
    try {
      await api(`/admin/groups/${id}`, { method: "DELETE" });
      router.push("/admin/groups");
    } catch (err) {
      setMsg({ ok: false, text: errorMessage(err) });
      setConfirm(false);
    }
  }

  if (error) return <p className="text-destructive">{error}</p>;
  if (!group) return <p className="text-muted-foreground">Loading…</p>;

  return (
    <>
      <PageHeader title={group.name} back={{ href: "/admin/groups", label: "Groups" }} />
      <Card>
        <CardHeader>
          <CardTitle>Details</CardTitle>
        </CardHeader>
        <CardContent>
          <GroupForm key={group.id} group={group} onSave={save} />
          <Status msg={msg} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Members ({group.members.length})</CardTitle>
          <CardDescription>To add or remove someone, open the user&apos;s Permissions page.</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="grid gap-2 sm:grid-cols-2">
            {group.members.map((u) => (
              <li key={u.id}>
                <Link
                  href={`/admin/users/${u.id}/permissions`}
                  className="flex items-center gap-2 rounded-lg border p-2 hover:bg-muted"
                >
                  <Avatar user={u} size={28} />
                  <span className="text-sm">{u.display_name}</span>
                  <span className="text-xs text-muted-foreground">@{u.username}</span>
                </Link>
              </li>
            ))}
            {group.members.length === 0 && <li className="text-sm text-muted-foreground">No members yet.</li>}
          </ul>
        </CardContent>
      </Card>

      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle className="text-destructive">Danger zone</CardTitle>
          <CardDescription>
            Deleting the group also deletes its {group.work_count} work(s) with all their messages and likes.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="destructive" onClick={() => setConfirm(true)}>
            Delete group
          </Button>
        </CardContent>
      </Card>

      <AlertDialog open={confirm} onOpenChange={setConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete &quot;{group.name}&quot;?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently deletes the group, its {group.work_count} work(s), and all their messages and likes. This
              can&apos;t be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <Button variant="destructive" onClick={remove}>
              Delete everything
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function GroupForm({
  group,
  onSave,
}: {
  group: GroupDetail;
  onSave: (form: { name: string; description: string }) => Promise<void>;
}) {
  const [form, setForm] = useState({ name: group.name, description: group.description });
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSave(form);
      }}
      className="mb-2 space-y-4"
    >
      <div className="space-y-1.5">
        <Label htmlFor="name">Name</Label>
        <Input id="name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="desc">Description</Label>
        <Textarea
          id="desc"
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
        />
      </div>
      <Button type="submit">Save</Button>
    </form>
  );
}
