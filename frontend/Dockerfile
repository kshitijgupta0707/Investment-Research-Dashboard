# The Next.js app.
#
# Used by docker-compose for a one-command local run. A Vercel deployment does
# not use this file -- Vercel builds Next.js natively from the repo.
#
# Three stages, so the shipped image carries neither the npm cache nor the
# toolchain that produced the build. Build context is `frontend/`.

# --- dependencies -----------------------------------------------------------

FROM node:22-slim AS deps
WORKDIR /app

# Only the manifests, so this layer stays cached until a dependency actually
# changes. `npm ci` over `npm install`: it installs exactly the lockfile and
# fails if the two have drifted, rather than quietly resolving something else.
COPY package.json package-lock.json ./
RUN npm ci

# --- build ------------------------------------------------------------------

FROM node:22-slim AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# NEXT_PUBLIC_* values are inlined into the bundle at build time, not read from
# the environment at boot. They therefore have to arrive as build args -- and
# changing one means rebuilding the image, not restarting the container.
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL \
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=$NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY

# NEXT_DIST_DIR is left unset on purpose: the standalone output is read from
# `.next/` in the next stage, and redirecting the build would move it.
RUN npm run build

# --- runtime ----------------------------------------------------------------

FROM node:22-slim AS runner
WORKDIR /app

# HOSTNAME matters: Next binds loopback by default, which inside a container
# means nothing outside it can connect.
ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# No user is created here: node:20-slim already ships a `node` user at uid 1000,
# and adding a second one at the same uid fails the build outright.

# `standalone` is a self-contained server carrying only the dependencies
# actually reached at runtime, plus its own server.js entrypoint. Static assets
# are not part of it and are copied separately.
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static

USER node

EXPOSE 3000

CMD ["node", "server.js"]
