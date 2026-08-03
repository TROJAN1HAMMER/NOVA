# syntax=docker/dockerfile:1
#
# Multi-stage: Vite build produces static assets; nginx serves them. Vite
# bakes VITE_* env vars in at build time (not readable at container
# startup), so the backend API URL is a build ARG here, not a runtime env
# var — set it via `--build-arg VITE_API_URL=...` or the Helm chart's
# corresponding value, which templates it into the image build in CI.

# ── Build ─────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app

# Separate layer from the source copy below so `npm ci` is only re-run
# when package-lock.json actually changes, not on every source edit.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

# ── Serve ─────────────────────────────────────────────────────────────────────
# nginx-unprivileged: pre-configured to run as a non-root user and listen
# on an unprivileged port (8080) — avoids hand-rolling chown/chmod fixes
# for nginx's default PID/cache/log directories that a plain nginx:alpine
# image would otherwise need to run as non-root.
FROM nginxinc/nginx-unprivileged:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

# `127.0.0.1`, not `localhost`: this image's /etc/hosts resolves
# "localhost" to the IPv6 loopback (::1) first, but nginx's `listen 8080;`
# only binds IPv4 — wget would try ::1, get connection-refused, and never
# fall back to 127.0.0.1, permanently marking the container unhealthy
# despite nginx serving real traffic correctly the whole time.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
