# Brewing API — production container.
# Host-agnostic: runs on Railway, Render, Fly, Cloud Run, etc.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for layer caching.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# App source.
COPY app ./app

# The platform injects $PORT; default to 8000 for local `docker run`.
ENV API_PORT=8000
EXPOSE 8000

# Tables are created on startup via the FastAPI lifespan (init_db()).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-${API_PORT:-8000}}"]
