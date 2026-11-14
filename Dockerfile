# AI YouTube Automation Pro - container for Railway (or any Docker host)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    YTAUTO_HOST=0.0.0.0 \
    YTAUTO_DATA_DIR=/app/storage/data \
    YTAUTO_PROJECTS_DIR=/app/storage/projects \
    YTAUTO_ENV_FILE=/app/storage/.env \
    GOOGLE_CLIENT_SECRETS_FILE=/app/storage/data/secrets/client_secret.json

# fonts for captions/thumbnails, espeak-ng for the offline 'sapi' voice provider
RUN apt-get update \
 && apt-get install -y --no-install-recommends fonts-dejavu-core espeak-ng \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN mkdir -p /app/storage

EXPOSE 8000
# The server refuses to start on 0.0.0.0 without APP_PASSWORD (set it in Railway > Variables).
CMD ["python", "-m", "ytauto", "serve"]
