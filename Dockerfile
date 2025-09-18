# -------- Frontend build stage --------
FROM node:18-alpine AS frontend-builder
WORKDIR /app
# Copy frontend and build
COPY webapp-frontend/ /app/webapp-frontend/
RUN cd /app/webapp-frontend \
 && (npm ci || npm install) \
 && npm run build

# -------- Backend runtime stage --------
FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src
WORKDIR /app

# System deps (optional: for building wheels if needed)
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# Copy project
COPY . /app
# Copy built frontend artifacts
COPY --from=frontend-builder /app/webapp-frontend/dist /app/webapp-frontend/dist

# Install Python dependencies via PEP 621 (pyproject.toml)
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir .

EXPOSE 5000
CMD ["python", "-m", "app.main"]
