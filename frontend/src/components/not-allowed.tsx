import Link from "next/link";
import { ShieldAlert } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";

export function NotAllowed({ message }: { message: string }) {
  return (
    <div className="mx-auto mt-16 max-w-md space-y-4 rounded-xl border bg-card p-8 text-center">
      <ShieldAlert className="mx-auto size-10 text-destructive" />
      <h1 className="text-lg font-semibold">You&apos;re not allowed to view this</h1>
      <p className="text-sm text-muted-foreground">{message}</p>
      <Link href="/" className={buttonVariants({ variant: "outline" })}>
        Back to home
      </Link>
    </div>
  );
}
