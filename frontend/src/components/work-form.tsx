"use client";

import Link from "next/link";
import { useState } from "react";
import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { errorMessage } from "@/lib/api";
import type { Group, WorkStatus } from "@/lib/types";

export type WorkFormValues = { group_id: number | ""; title: string; body: string; status: WorkStatus };

export function WorkForm({
  initial,
  groups,
  submitLabel,
  onSubmit,
  lockGroup,
}: {
  initial: WorkFormValues;
  groups: Group[];
  submitLabel: string;
  onSubmit: (v: WorkFormValues) => Promise<void>;
  lockGroup?: boolean;
}) {
  const [v, setV] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit(v);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (groups.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        A work belongs to a group.{" "}
        <Link href="/admin/groups/new" className="text-primary underline">
          Create a group first
        </Link>
        .
      </p>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-[1fr_160px]">
        <div className="space-y-1.5">
          <Label htmlFor="group">Group</Label>
          <select
            id="group"
            required
            disabled={lockGroup}
            value={v.group_id}
            onChange={(e) => setV({ ...v, group_id: e.target.value ? Number(e.target.value) : "" })}
            className="h-8 w-full rounded-lg border border-input bg-input/30 px-2.5 text-sm disabled:opacity-60"
          >
            <option value="">Choose a group…</option>
            {groups.map((g) => (
              <option key={g.id} value={g.id}>
                {g.name}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="status">Status</Label>
          <select
            id="status"
            value={v.status}
            onChange={(e) => setV({ ...v, status: e.target.value as WorkStatus })}
            className="h-8 w-full rounded-lg border border-input bg-input/30 px-2.5 text-sm"
          >
            <option value="open">Open</option>
            <option value="closed">Closed (read-only)</option>
          </select>
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="title">Title</Label>
        <Input
          id="title"
          value={v.title}
          onChange={(e) => setV({ ...v, title: e.target.value })}
          required
          maxLength={200}
        />
      </div>
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <Label htmlFor="body">Description (Markdown)</Label>
          <button type="button" className="text-xs text-primary" onClick={() => setPreview(!preview)}>
            {preview ? "Edit" : "Preview"}
          </button>
        </div>
        {preview ? (
          <div className="min-h-32 rounded-lg border p-3 text-sm">
            <Markdown>{v.body || "_Nothing to preview_"}</Markdown>
          </div>
        ) : (
          <Textarea
            id="body"
            rows={8}
            value={v.body}
            onChange={(e) => setV({ ...v, body: e.target.value })}
            placeholder="What should the group work on together?"
          />
        )}
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button type="submit" disabled={busy}>
        {busy ? "Saving…" : submitLabel}
      </Button>
    </form>
  );
}
