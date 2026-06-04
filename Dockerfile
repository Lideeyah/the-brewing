# Brewing API — root-level production container.
# Builds from the repo root so Render works with default settings
# (empty Root Directory, Dockerfile Path = ./Dockerfile). The build context is
# the repo root; only the api/ sources are copied into the image.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for layer caching.
COPY api/requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# App source.
COPY api/app ./app

# The platform injects $PORT; default to 8000 for local `docker run`.
ENV API_PORT=8000
EXPOSE 8000

# Tables are created on startup via the FastAPI lifespan (init_db()).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-${API_PORT:-8000}}"]
