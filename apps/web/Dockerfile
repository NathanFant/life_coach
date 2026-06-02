# Build stage
FROM node:22-alpine AS builder

WORKDIR /app

# Copy monorepo files
COPY package.json pnpm-lock.yaml ./
COPY apps/web ./apps/web
COPY packages ./packages

# Install pnpm
RUN npm install -g pnpm@9

# Install dependencies
RUN pnpm install --frozen-lockfile

# Build web app
WORKDIR /app/apps/web
RUN pnpm build

# Runtime stage
FROM node:22-alpine AS runtime

WORKDIR /app/apps/web

# Install pnpm
RUN npm install -g pnpm@9

# Copy built app and dependencies from builder
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/apps/web/.next ./.next
COPY --from=builder /app/apps/web/public ./public
COPY --from=builder /app/apps/web/package.json ./package.json

EXPOSE 3000

CMD ["pnpm", "start"]
