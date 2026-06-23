# AI Gateway (NestJS) image (Day 13). Multi-stage: build with full toolchain, ship a
# slim non-root runtime with prod node_modules + compiled dist only.
#
#   docker build -t secops-gateway services/gateway
# syntax=docker/dockerfile:1

FROM node:20-slim AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY tsconfig.json tsconfig.build.json nest-cli.json ./
COPY src ./src
RUN npm run build && npm prune --omit=dev

FROM node:20-slim AS runtime
ENV NODE_ENV=production PORT=3000
RUN useradd --create-home --uid 10001 appuser
WORKDIR /app
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY package.json ./
USER appuser
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||3000)+'/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "dist/main.js"]
