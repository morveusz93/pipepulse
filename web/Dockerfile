FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node:22-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
# Only used for the /api rewrite (dev / docker-compose); see next.config.ts.
ARG PIPEPULSE_API_URL=http://api:8000
ENV PIPEPULSE_API_URL=$PIPEPULSE_API_URL
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
RUN addgroup -S -g 10001 pipepulse && adduser -S -u 10001 -G pipepulse pipepulse
COPY --from=build --chown=pipepulse:pipepulse /app/.next/standalone ./
COPY --from=build --chown=pipepulse:pipepulse /app/.next/static ./.next/static
COPY --from=build --chown=pipepulse:pipepulse /app/public ./public
USER pipepulse
EXPOSE 3000
# PIPEPULSE_API_URL at runtime: where server components fetch data from.
CMD ["node", "server.js"]
