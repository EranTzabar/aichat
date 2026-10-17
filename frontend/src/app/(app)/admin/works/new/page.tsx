"use client";

import { useRouter } from "next/navigation";
import { PageHeader, useFetch } from "@/components/admin";
import { Card, CardContent } from "@/components/ui/card";
import { saveWorkFiles, WorkForm } from "@/components/work-form";
import { api } from "@/lib/api";
import type { Group, Work } from "@/lib/types";

export default function NewWorkPage() {
  const router = useRouter();
  const { data: groups } = useFetch<Group[]>("/admin/groups");

  return (
    <>
      <PageHeader
        title="New work"
        description="Group members will see it under “New in my groups”."
        back={{ href: "/admin/works", label: "Works" }}
      />
      <Card>
        <CardContent>
          {groups ? (
            <WorkForm
              groups={groups}
              initial={{ group_id: "", title: "", body: "", status: "open" }}
              submitLabel="Create work"
              onSubmit={async (v, files) => {
                const work = await api<Work>("/admin/works", { json: v });
                if (files.add.length) await saveWorkFiles(work.id, files);
                router.push(`/works/${work.id}`);
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
