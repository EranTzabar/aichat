"use client";

import { AvatarUpload } from "@/components/avatar-upload";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useMe } from "@/lib/auth";

export default function SettingsPage() {
  const me = useMe();
  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <h1 className="text-2xl font-semibold">Settings</h1>
      <Card>
        <CardHeader>
          <CardTitle>My icon</CardTitle>
          <CardDescription>Shown next to your messages in every chat.</CardDescription>
        </CardHeader>
        <CardContent>
          <AvatarUpload user={me} endpoint="/me/avatar" />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>Only the admin can change your name, bio, groups or password.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div>
            <span className="text-muted-foreground">Name:</span> {me.display_name}
          </div>
          <div>
            <span className="text-muted-foreground">Username:</span> @{me.username}
          </div>
          {me.bio && (
            <div>
              <span className="text-muted-foreground">Bio:</span> {me.bio}
            </div>
          )}
          <div>
            <span className="text-muted-foreground">Groups:</span> {me.groups.map((g) => g.name).join(", ") || "none"}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
