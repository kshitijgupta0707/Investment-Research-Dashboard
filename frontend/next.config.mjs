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

  /*
   * Emit a self-contained server bundle at `${distDir}/standalone`, carrying
   * only the dependencies actually reached at runtime. The Docker image copies
   * that instead of the whole `node_modules`, which is the difference between
   * an image around 200 MB and one well over a gigabyte.
   *
   * No effect on `next dev` or on a Vercel deployment -- both ignore it.
   */
  output: "standalone",
};

export default nextConfig;
