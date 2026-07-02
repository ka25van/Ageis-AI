#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/aegis"
ENV_FILE="${APP_DIR}/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: .env file not found at $ENV_FILE"
    echo "Copy .env.example to $ENV_FILE and fill in the values"
    exit 1
fi

echo "=== Pulling latest images ==="
docker compose -f "${APP_DIR}/docker-compose.yml" -f "${APP_DIR}/docker-compose.prod.yml" pull

echo "=== Starting services ==="
docker compose -f "${APP_DIR}/docker-compose.yml" -f "${APP_DIR}/docker-compose.prod.yml" up -d --remove-orphans

echo "=== Waiting for health checks ==="
sleep 10

echo "=== Pulling Ollama model ==="
docker exec aegis-ollama ollama pull nomic-embed-text || true
docker exec aegis-ollama ollama pull llama3.2 || true

echo "=== Cleaning up ==="
docker image prune -f

echo "=== Deployment complete ==="
echo "Frontend: https://app.aegis.ai"
echo "API:      https://api.aegis.ai"
echo "Health:   https://api.aegis.ai/health"
