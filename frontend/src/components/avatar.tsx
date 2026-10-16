"use client";

import { API_URL } from "@/lib/api";
import { useAvatarVersion } from "@/lib/avatar-version";
import { cn } from "@/lib/utils";

export function Avatar({
  user,
  size = 36,
  online,
  className,
}: {
  user: { id: number; display_name: string };
  size?: number;
  online?: boolean;
  className?: string;
}) {
  const v = useAvatarVersion();
  return (
    <span className={cn("relative inline-block shrink-0", className)} style={{ width: size, height: size }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={`${API_URL}/users/${user.id}/avatar?v=${v}`}
        alt={user.display_name}
        width={size}
        height={size}
        className="rounded-full object-cover bg-muted"
        style={{ width: size, height: size }}
      />
      {online !== undefined && (
        <span
          className={cn(
            "absolute right-0 bottom-0 block size-2.5 rounded-full ring-2 ring-card",
            online ? "bg-green-500" : "bg-muted-foreground/40",
          )}
        />
      )}
    </span>
  );
}
