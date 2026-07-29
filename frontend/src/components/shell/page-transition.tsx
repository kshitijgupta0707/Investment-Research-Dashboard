"use client";

import { motion, useReducedMotion } from "framer-motion";
import { usePathname } from "next/navigation";

/**
 * A short rise-and-fade as each page arrives.
 *
 * Keyed on the pathname so the animation replays on navigation. `children` is
 * passed as a prop, so it stays server-rendered.
 */
export function PageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const reduced = useReducedMotion();

  if (reduced) return <>{children}</>;

  return (
    <motion.div
      key={pathname}
      // `min-w-0` so a wide table scrolls internally instead of stretching
      // the grid column.
      className="min-w-0"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}
