#!/bin/bash
set -e

# Só rodamos as migrações se o container for o principal (API) para evitar concorrência
# O comando do compose para a API contém 'uvicorn'
if [[ "$*" == *"uvicorn"* ]]; then
  echo "🚀 Running database migrations..."
  alembic upgrade head
  echo "✅ Migrations completed!"
fi

# Executa o comando passado para o container (via CMD ou docker-compose command)
exec "$@"
