# ==========================================
# STAGE 1: Build React Application
# ==========================================
FROM node:20-alpine AS builder

# Pass build arguments
ARG VITE_API_URL
ARG VITE_WS_URL

# Set as environment variables for the build process
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_WS_URL=$VITE_WS_URL

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# ==========================================
# STAGE 2: Serve using Nginx
# ==========================================
FROM nginx:stable-alpine AS runner

COPY --from=builder /app/dist /usr/share/nginx/html

# Custom nginx conf inside frontend container to support SPA Routing
RUN echo 'server { \
    listen 80; \
    location / { \
        root /usr/share/nginx/html; \
        index index.html index.htm; \
        try_files $uri $uri/ /index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
