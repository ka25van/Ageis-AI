FROM node:20-alpine AS deps

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY tsconfig*.json vite.config.ts index.html ./
COPY public ./public
COPY src ./src

RUN npm run build

FROM nginx:1.27-alpine AS runner

RUN apk add --no-cache curl

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
