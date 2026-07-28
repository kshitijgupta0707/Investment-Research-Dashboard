import { MarketPanel } from "@/components/market/market-panel";

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

      <main className="flex items-center justify-center px-6 py-8 lg:p-10">
        <div className="w-full max-w-[370px]">{children}</div>
      </main>
    </div>
  );
}
