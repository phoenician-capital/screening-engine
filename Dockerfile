# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install && chmod +x node_modules/.bin/*
COPY frontend/ .
RUN npm run build

# Stage 2: Build backend with frontend
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ src/
COPY .env.example .env

# Copy frontend dist files from builder
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Health check (increased grace period to 30s for app initialization)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/screening/status || exit 1

# Run API
EXPOSE 8000
CMD ["uvicorn", "src.mcp_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
