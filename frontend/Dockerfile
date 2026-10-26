FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
COPY scripts ./scripts
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app
# Rewrites (/api/* -> backend) are resolved at build time.
ARG API_INTERNAL_URL=http://api:8000
ARG NEXT_PUBLIC_BASEMAP_STYLE=
ENV API_INTERNAL_URL=$API_INTERNAL_URL NEXT_PUBLIC_BASEMAP_STYLE=$NEXT_PUBLIC_BASEMAP_STYLE NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN node scripts/copy-maplibre-worker.mjs && npm run build

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup -S web && adduser -S web -G web
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
USER web
EXPOSE 3000
CMD ["node", "server.js"]
