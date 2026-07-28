import { BrandMark } from "@/components/brand/brand-mark";
import { Button } from "@/components/ui/button";
import { logout } from "@/lib/auth/actions";

/**
 * Signed in, but not a member of any organization.
 *
 * Reachable when signup created the Supabase account and then failed before
 * provisioning -- a browser closed mid-flow, or the backend was down. The
 * account is real, so signing out and starting again is the way through; the
 * address is already taken, which is why this says so rather than silently
 * sending them back to a signup form that would reject them.
 */
export function FinishSetup() {
  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-[420px]">
        <BrandMark />

        <h1 className="mt-8 font-display text-2xl font-medium tracking-[-0.025em]">
          Your account isn&apos;t in a workspace yet
        </h1>

        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          The account exists, but it was never joined to an organization — signup was
          probably interrupted. Sign out and create the workspace again, or ask an admin
          for an invite code.
        </p>

        <form action={logout}>
          <Button type="submit" className="mt-6 h-[42px] w-full font-semibold">
            Sign out and start over
          </Button>
        </form>
      </div>
    </main>
  );
}
