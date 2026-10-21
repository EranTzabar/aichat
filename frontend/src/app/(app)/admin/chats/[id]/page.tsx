"use client";

import { useParams, useRouter } from "next/navigation";
import { PageHeader, useFetch } from "@/components/admin";
import { Card, CardContent } from "@/components/ui/card";
import { automationOf, automationPayload } from "@/components/chat-automation";
import { saveChatFiles, ChatForm } from "@/components/chat-form";
import type { Group, ChatState } from "@/lib/types";

export default function EditChatPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: groups } = useFetch<Group[]>("/admin/groups");
  const { data: state, error } = useFetch<ChatState>(`/chats/${id}`);

  return (
    <>
      <PageHeader title="Edit chat" back={{ href: "/admin/chats", label: "Chats" }} />
      {error && <p className="text-destructive">{error}</p>}
      <Card>
        <CardContent>
          {groups && state ? (
            <ChatForm
              groups={groups}
              lockGroup
              initial={{
                group_id: state.chat.group.id,
                title: state.chat.title,
                body: state.chat.body,
                status: state.chat.status,
                auto: automationOf(state.chat),
              }}
              existing={state.chat.attachments ?? []}
              submitLabel="Save"
              onSubmit={async (v, files) => {
                await saveChatFiles(Number(id), files, {
                  title: v.title,
                  body: v.body,
                  status: v.status,
                  ...automationPayload(v.auto),
                });
                router.push(`/chats/${id}`);
              }}
            />
          ) : (
            !error && <p className="text-muted-foreground">Loading…</p>
          )}
        </CardContent>
      </Card>
    </>
  );
}
