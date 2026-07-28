import type { Metadata } from "next";
import { Suspense } from "react";

import { LoginForm } from "@/components/auth/login-form";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  // The form reads `next` from the query string, which needs a Suspense
  // boundary so the rest of the shell can still render statically.
  return (
    <Suspense fallback={<Skeleton className="h-[420px] w-full" />}>
      <LoginForm />
    </Suspense>
  );
}
