"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { Copy, RefreshCw } from "lucide-react";
import { useFetch } from "@/components/admin";
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
import { API_URL, api } from "@/lib/api";
import type { ApiToken } from "@/lib/types";

export default function TokenPage() {
  const { id } = useParams<{ id: string }>();
  const { data, error, setData } = useFetch<ApiToken>(`/admin/users/${id}/api-token`);
  const [confirm, setConfirm] = useState(false);
  const [copied, setCopied] = useState(false);

  async function regenerate() {
    setData(await api<ApiToken>(`/admin/users/${id}/api-token/regenerate`, { method: "POST" }));
    setConfirm(false);
  }

  async function copy() {
    if (!data) return;
    await navigator.clipboard.writeText(data.token);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  if (error) return <p className="text-destructive">{error}</p>;
  if (!data) return <p className="text-muted-foreground">Loading…</p>;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>API token</CardTitle>
          <CardDescription>
            Long-lived JWT (version {data.token_version}). Anyone holding it acts as this user through the API.
            {!data.api_enabled && (
              <span className="text-destructive"> API access is currently disabled for this user.</span>
            )}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <pre className="overflow-x-auto rounded-lg bg-muted p-3 font-mono text-xs break-all whitespace-pre-wrap">
            {data.token}
          </pre>
          <div className="flex gap-2">
            <Button variant="outline" onClick={copy}>
              <Copy className="size-4" /> {copied ? "Copied!" : "Copy"}
            </Button>
            <Button variant="destructive" onClick={() => setConfirm(true)}>
              <RefreshCw className="size-4" /> Regenerate
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Try it</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="overflow-x-auto rounded-lg bg-muted p-3 font-mono text-xs">{`# list works
curl -H "Authorization: Bearer $TOKEN" ${API_URL}/works

# full state of work 1
curl -H "Authorization: Bearer $TOKEN" ${API_URL}/works/1

# reply to message 5
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \\
  -d '{"body":"Sounds good!"}' ${API_URL}/messages/5/replies`}</pre>
          <p className="mt-2 text-xs text-muted-foreground">
            Full interactive docs:{" "}
            <a
              className="text-primary underline"
              href={API_URL.replace(/\/api\/v1$/, "") + "/docs"}
              target="_blank"
              rel="noreferrer"
            >
              /docs
            </a>
          </p>
        </CardContent>
      </Card>

      <AlertDialog open={confirm} onOpenChange={setConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Regenerate API token?</AlertDialogTitle>
            <AlertDialogDescription>
              The current token stops working immediately. Any bot using it will get 401 token_revoked.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <Button variant="destructive" onClick={regenerate}>
              Regenerate
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
