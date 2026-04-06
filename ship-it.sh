#!/bin/bash
set -e

# Cores para o terminal
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[ NC'

# Verificar se o usuário quer resetar os volumes
RESET_VOLUMES=false
for arg in "$@"; do
    if [ "$arg" == "--reset" ]; then
        RESET_VOLUMES=true
    fi
done

echo -e "${BLUE}==== 🚀 PAYMENT ORCHESTRATOR - DEPLOY AWS (Ohio) ====${NC}"

# 1. Provisionar Infraestrutura
echo -e "${YELLOW}1. Provisionando infraestrutura via Terraform...${NC}"
cd terraform/aws
chmod +x deploy.sh
./deploy.sh

# Capturar o IP da nova instância
IP=$(terraform output -raw instance_public_ip)
cd ../..

echo -e "${GREEN}Instância pronta no IP: $IP${NC}"

# 2. Aguardar SSH
echo -e "${YELLOW}2. Aguardando conexão SSH...${NC}"
until ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no ubuntu@$IP exit 2>/dev/null; do
    echo -n "."
    sleep 5
done
echo -e "\n${GREEN}Conectado!${NC}"

# 3. VM Setup
echo -e "${YELLOW}3. Preparando diretório remoto...${NC}"
ssh -o StrictHostKeyChecking=no ubuntu@$IP "sudo mkdir -p /opt/payment-orchestrator && sudo chown -R ubuntu:ubuntu /opt/payment-orchestrator"

# 4. Sincronizar Código
echo -e "${YELLOW}4. Enviando arquivos (Sincronização incremental)...${NC}"
rsync -avz -e "ssh -o StrictHostKeyChecking=no" \
    --exclude '.venv' \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '.pytest_cache' \
    --exclude 'terraform' \
    --exclude 'migrations/versions_backup' \
    ./ ubuntu@$IP:/opt/payment-orchestrator/

# 5. Remote Build e Run
echo -e "${YELLOW}5. Executando comandos remotos na VM...${NC}"
ssh -o StrictHostKeyChecking=no ubuntu@$IP << EOF
    cd /opt/payment-orchestrator
    if [ ! -f .env ]; then cp .env.example .env; fi
    
    # SSL Setup
    mkdir -p ssl
    if [ ! -f ssl/server.key ]; then
        echo "Gerando certificados SSL auto-assinados..."
        sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout ssl/server.key -out ssl/server.crt \
            -subj "/C=BR/ST=OH/L=Columbus/O=Dev/CN=localhost"
        sudo chown ubuntu:ubuntu ssl/server.key ssl/server.crt
    fi

    # Docker Operations
    if [ "$RESET_VOLUMES" = true ]; then
        echo -e "${RED}LIMPANDO VOLUMES E FILAS (HARD RESET)...${NC}"
        sudo docker compose -f docker-compose.yaml -f docker-compose.prod.yaml down -v
    else
        sudo docker compose -f docker-compose.yaml -f docker-compose.prod.yaml down
    fi

    echo "Building containers..."
    sudo docker compose -f docker-compose.yaml -f docker-compose.prod.yaml build --pull
    
    echo "Subindo serviços..."
    sudo docker compose -f docker-compose.yaml -f docker-compose.prod.yaml up -d
    
    echo "Aguardando inicialização do DB (30s)..."
    sleep 30
    
    echo "Rodando migrações (Novo Schema Unificado)..."
    sudo docker compose -f docker-compose.yaml -f docker-compose.prod.yaml exec -T api alembic upgrade head
    
    if [ "$RESET_VOLUMES" = true ]; then
        echo "Limpando mensagens residuais do RabbitMQ..."
        sudo docker compose -f docker-compose.yaml -f docker-compose.prod.yaml exec -T worker celery -A app.infra.worker.app purge -f
    fi
EOF

echo -e "${GREEN}==== ✅ DEPLOY CONCLUÍDO COM SUCESSO! ====${NC}"
echo -e "${BLUE}API (Saúde):${NC} https://$IP/health"
echo -e "${BLUE}Dashboard:${NC} https://$IP/grafana/"
echo -e "${YELLOW}Dica: rode com --reset se alterou o esquema do banco ou quer zerar métricas.${NC}"
