/** @type {import('next').NextConfig} */
const nextConfig = {
  /*
   * `next dev` and `next build` both own `.next`, so running a build while the
   * dev server is up corrupts it and the running app starts 404ing its own
   * chunks. Setting NEXT_DIST_DIR sends a build somewhere else, which makes it
   * safe to verify a build without interrupting whoever is testing.
   *
   *   NEXT_DIST_DIR=.next-build npm run build
   */
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
