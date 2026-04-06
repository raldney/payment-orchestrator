#!/bin/bash
set -e

echo "Iniciando setup da VM do Payment Orchestrator..."

# 1. Atualizar sistema
apt-get update
apt-get upgrade -y

# 2. Instalar dependências básicas
apt-get install -y ca-certificates curl gnupg git software-properties-common wget

# 3. Instalar Docker
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 4. Criar diretório do app
APP_DIR="/opt/payment-orchestrator"
mkdir -p $APP_DIR

# 5. Permissões
chown -R $USER:$USER $APP_DIR
usermod -aG docker $USER

echo "Setup concluído! Certifique-se de colocar seus arquivos no /opt/payment-orchestrator e rodar 'docker compose up -d'"
