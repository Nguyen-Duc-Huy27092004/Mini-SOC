# Docker Compose Production Deployment Blueprint
## Enterprise Mini SOC Platform

### 1. Production Docker Compose Topology (`docker-compose.production.yml`)

```yaml
version: '3.8'

networks:
  mini-soc-network:
    driver: bridge

volumes:
  postgres_data:
  redis_data:
  nginx_logs:

services:
  postgres:
    image: postgres:16-alpine
    container_name: mini-soc-postgres
    restart: always
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-minisoc}
      POSTGRES_USER: ${POSTGRES_USER:-minisoc}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Required}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - mini-soc-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-minisoc}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: mini-soc-redis
    restart: always
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD:?Required}
    volumes:
      - redis_data:/data
    networks:
      - mini-soc-network
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: mini-soc-backend
    restart: always
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      JWT_SECRET: ${JWT_SECRET:?Required}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - mini-soc-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 15s
      timeout: 5s
      retries: 3

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: mini-soc-frontend
    restart: always
    networks:
      - mini-soc-network

  nginx:
    image: nginx:1.25-alpine
    container_name: mini-soc-nginx
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
      - nginx_logs:/var/log/nginx
    depends_on:
      - backend
      - frontend
    networks:
      - mini-soc-network
```
