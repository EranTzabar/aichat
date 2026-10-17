"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { Paperclip, X } from "lucide-react";
import { Markdown } from "@/components/markdown";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api, errorMessage, fileSize, uploadFile } from "@/lib/api";
import type { Attachment, Group, WorkStatus } from "@/lib/types";

const SELECT_CLASS =
  "h-8 w-full rounded-lg border border-input bg-input/30 px-2.5 text-sm text-foreground outline-none " +
  "focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-60";

export type WorkFormValues = { group_id: number | ""; title: string; body: string; status: WorkStatus };
/** Files to upload and attach to the work post, and existing ones to delete. */
export type WorkFormFiles = { add: File[]; remove: number[] };

/** Upload the new files to the work and attach them / delete the removed ones, in one PATCH. */
export async function saveWorkFiles(workId: number, files: WorkFormFiles, fields: object = {}) {
  const ids = [];
  for (const file of files.add) ids.push((await uploadFile(workId, file)).id);
  await api(`/admin/works/${workId}`, {
    method: "PATCH",
    json: { ...fields, attachment_ids: ids, remove_attachment_ids: files.remove },
  });
}

export function WorkForm({
  initial,
  groups,
  submitLabel,
  onSubmit,
  lockGroup,
  existing = [],
}: {
  initial: WorkFormValues;
  groups: Group[];
  submitLabel: string;
  onSubmit: (v: WorkFormValues, files: WorkFormFiles) => Promise<void>;
  lockGroup?: boolean;
  existing?: Attachment[];
}) {
  const [v, setV] = useState(initial);
  const [added, setAdded] = useState<File[]>([]);
  const [removed, setRemoved] = useState<number[]>([]);
  const fileInput = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit(v, { add: added, remove: removed });
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
            className={SELECT_CLASS}
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
            className={SELECT_CLASS}
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
      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <Label>Files</Label>
          <button type="button" className="inline-flex items-center gap-1 text-xs text-primary" onClick={() => fileInput.current?.click()}>
            <Paperclip className="size-3.5" /> Add files
          </button>
          <input
            ref={fileInput}
            type="file"
            multiple
            hidden
            onChange={(e) => {
              const picked = Array.from(e.target.files ?? []);
              setAdded((list) => [...list, ...picked]);
              e.target.value = "";
            }}
          />
        </div>
        <div
          className="flex min-h-12 flex-wrap gap-2 rounded-lg border border-dashed p-2"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const dropped = Array.from(e.dataTransfer.files);
            setAdded((list) => [...list, ...dropped]);
          }}
        >
          {existing
            .filter((a) => !removed.includes(a.id))
            .map((a) => (
              <FileChip key={`a${a.id}`} name={a.filename} size={a.size} onRemove={() => setRemoved((r) => [...r, a.id])} />
            ))}
          {added.map((f, i) => (
            <FileChip
              key={`f${i}-${f.name}`}
              name={f.name}
              size={f.size}
              isNew
              onRemove={() => setAdded((list) => list.filter((x) => x !== f))}
            />
          ))}
          {existing.length - removed.length + added.length === 0 && (
            <span className="self-center px-1 text-xs text-muted-foreground">
              Images, audio, video or any file. Drop them here or use “Add files”.
            </span>
          )}
        </div>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button type="submit" disabled={busy}>
        {busy ? "Saving…" : submitLabel}
      </Button>
    </form>
  );
}

function FileChip({ name, size, isNew, onRemove }: { name: string; size: number; isNew?: boolean; onRemove: () => void }) {
  return (
    <span className="inline-flex max-w-60 items-center gap-1.5 rounded-md border bg-background px-2 py-1 text-xs">
      <Paperclip className="size-3 shrink-0 text-muted-foreground" />
      <span className="truncate">{name}</span>
      <span className="shrink-0 text-muted-foreground">
        {fileSize(size)}
        {isNew && " · new"}
      </span>
      <button type="button" onClick={onRemove} title="Remove" className="rounded p-0.5 hover:bg-muted">
        <X className="size-3" />
      </button>
    </span>
  );
}
