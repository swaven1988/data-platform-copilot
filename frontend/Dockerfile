FROM node:20-alpine AS builder
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# -----------------------------
# Production runtime
# -----------------------------
FROM nginx:1.27-alpine

COPY --from=builder /app/dist /usr/share/nginx/html

# Use custom nginx config that includes try_files for SPA routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Non-root nginx (already runs as nginx user in alpine image)
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]