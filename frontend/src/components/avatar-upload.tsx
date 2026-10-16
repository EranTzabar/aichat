"use client";

import { useRef, useState } from "react";
import { Avatar } from "@/components/avatar";
import { Button } from "@/components/ui/button";
import { api, avatarProblem, errorMessage } from "@/lib/api";
import { bumpAvatarVersion } from "@/lib/avatar-version";

/** Upload an icon to `endpoint` (POST multipart `file`). */
export function AvatarUpload({ user, endpoint }: { user: { id: number; display_name: string }; endpoint: string }) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function onFile(file: File | undefined) {
    if (!file) return;
    const problem = avatarProblem(file);
    if (problem) {
      setMsg({ ok: false, text: problem });
      if (input.current) input.current.value = "";
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      const form = new FormData();
      form.append("file", file);
      await api(endpoint, { form });
      bumpAvatarVersion();
      setMsg({ ok: true, text: "Icon updated." });
    } catch (e) {
      setMsg({ ok: false, text: errorMessage(e) });
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  return (
    <div className="flex items-center gap-4">
      <Avatar user={user} size={72} />
      <div className="space-y-1">
        <input
          ref={input}
          type="file"
          accept="image/png,image/jpeg,image/gif,image/webp"
          className="hidden"
          onChange={(e) => onFile(e.target.files?.[0])}
        />
        <Button variant="outline" size="sm" disabled={busy} onClick={() => input.current?.click()}>
          {busy ? "Uploading…" : "Change icon"}
        </Button>
        <p className="text-xs text-muted-foreground">PNG, JPEG, GIF or WEBP, up to 2 MB.</p>
        {msg && <p className={msg.ok ? "text-xs text-green-500" : "text-xs text-destructive"}>{msg.text}</p>}
      </div>
    </div>
  );
}
