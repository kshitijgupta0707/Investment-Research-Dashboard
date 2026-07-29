import { MarketPanel } from "@/components/market/market-panel";
import { ThemeToggle } from "@/components/theme/theme-toggle";

/**
 * The split sign-in screen: product panel on the left, form on the right.
 *
 * Both auth pages share it, so the panel mounts once and its animation is not
 * restarted when someone toggles between sign in and sign up.
 */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.08fr_1fr]">
      <MarketPanel />

      <main className="bg-aurora relative flex items-center justify-center px-6 py-8 lg:p-10">
        {/* Sits over the form column rather than the panel, so it is reachable
            before anyone has an account and never overlaps the wordmark. */}
        <ThemeToggle className="absolute right-4 top-4 lg:right-6 lg:top-6" />
        <div className="w-full max-w-[370px]">{children}</div>
      </main>
    </div>
  );
}
