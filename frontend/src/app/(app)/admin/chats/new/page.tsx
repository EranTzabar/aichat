"use client";

import { useRouter } from "next/navigation";
import { PageHeader, useFetch } from "@/components/admin";
import { Card, CardContent } from "@/components/ui/card";
import { automationPayload, NO_AUTOMATION } from "@/components/chat-automation";
import { saveChatFiles, ChatForm } from "@/components/chat-form";
import { api } from "@/lib/api";
import type { Group, Chat } from "@/lib/types";

export default function NewChatPage() {
  const router = useRouter();
  const { data: groups } = useFetch<Group[]>("/admin/groups");

  return (
    <>
      <PageHeader
        title="New chat"
        description="Group members will see it under “New in my groups”."
        back={{ href: "/admin/chats", label: "Chats" }}
      />
      <Card>
        <CardContent>
          {groups ? (
            <ChatForm
              groups={groups}
              initial={{ group_id: "", title: "", body: "", status: "open", auto: NO_AUTOMATION }}
              submitLabel="Create chat"
              onSubmit={async (v, files) => {
                const { auto, ...fields } = v;
                const chat = await api<Chat>("/admin/chats", { json: { ...fields, ...automationPayload(auto) } });
                if (files.add.length) await saveChatFiles(chat.id, files);
                router.push(`/chats/${chat.id}`);
              }}
            />
          ) : (
            <p className="text-muted-foreground">Loading…</p>
          )}
        </CardContent>
      </Card>
    </>
  );
}
