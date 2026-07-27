# ---- build React UI ----
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
# Empty base URL => browser calls same-origin /api (served by FastAPI)
ENV VITE_API_BASE_URL=
RUN npm run build

# ---- API + static UI ----
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY data ./data
COPY --from=web /web/dist ./frontend/dist

ENV PYTHONUNBUFFERED=1
ENV SERVE_FRONTEND=true
ENV CORS_ORIGINS=*
ENV TOKENIZERS_PARALLELISM=false
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV HF_HOME=/tmp/hf

EXPOSE 8000

# Railway/Render inject PORT; local/Docker default 8000
# Free tiers are slow to boot — long start-period
HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=5 \
  CMD python -c "import os,urllib.request; p=os.environ.get('PORT','8000'); urllib.request.urlopen(f'http://127.0.0.1:{p}/api/health')"

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
