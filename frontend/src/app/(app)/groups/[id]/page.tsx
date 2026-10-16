"use client";

import { useParams } from "next/navigation";
import { usePanelGroup } from "@/components/panel";
import { NotAllowed } from "@/components/not-allowed";
import { WorkSection } from "@/components/work-card";
import { useMe } from "@/lib/auth";
import { useWorks } from "@/lib/works";

export default function GroupPage() {
  const groupId = Number(useParams<{ id: string }>().id);
  const me = useMe();
  const { works } = useWorks();
  const group = me.groups.find((g) => g.id === groupId);
  usePanelGroup(group || me.is_admin ? groupId : null);

  if (!group && !me.is_admin) {
    return <NotAllowed message="You are not a member of this group. Ask the admin to add you." />;
  }
  const list = (works ?? []).filter((w) => w.group_id === groupId);
  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <h1 className="text-2xl font-semibold">{group?.name ?? list[0]?.group_name ?? "Group"}</h1>
      <WorkSection title="Works" works={list} empty="The admin hasn't created any work in this group yet." />
    </div>
  );
}
