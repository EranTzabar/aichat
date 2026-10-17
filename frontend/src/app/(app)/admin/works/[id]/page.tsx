"use client";

import { useParams, useRouter } from "next/navigation";
import { PageHeader, useFetch } from "@/components/admin";
import { Card, CardContent } from "@/components/ui/card";
import { saveWorkFiles, WorkForm } from "@/components/work-form";
import type { Group, WorkState } from "@/lib/types";

export default function EditWorkPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: groups } = useFetch<Group[]>("/admin/groups");
  const { data: state, error } = useFetch<WorkState>(`/works/${id}`);

  return (
    <>
      <PageHeader title="Edit work" back={{ href: "/admin/works", label: "Works" }} />
      {error && <p className="text-destructive">{error}</p>}
      <Card>
        <CardContent>
          {groups && state ? (
            <WorkForm
              groups={groups}
              lockGroup
              initial={{
                group_id: state.work.group.id,
                title: state.work.title,
                body: state.work.body,
                status: state.work.status,
              }}
              existing={state.work.attachments ?? []}
              submitLabel="Save"
              onSubmit={async (v, files) => {
                await saveWorkFiles(Number(id), files, { title: v.title, body: v.body, status: v.status });
                router.push(`/works/${id}`);
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
