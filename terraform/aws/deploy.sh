#!/bin/bash
set -e

# Cores para o output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}==== Iniciando Deploy Automatizado (AWS us-east-2) ====${NC}"

# 1. Entrar no Bootstrap e garantir o Bucket S3
echo -e "${BLUE}1. Garantindo infraestrutura de estado (S3 Bucket)...${NC}"
cd bootstrap
terraform init
terraform apply -auto-approve

# Captura o nome do bucket gerado pelo Terraform
BUCKET_NAME=$(terraform output -raw s3_bucket_name)
echo -e "${GREEN}Bucket detectado: $BUCKET_NAME${NC}"

# 2. Voltar e atualizar o backend.tfvars
cd ..
echo -e "${BLUE}2. Atualizando backend.tfvars com o novo bucket...${NC}"

cat <<EOF > backend.tfvars
bucket       = "$BUCKET_NAME"
key          = "aws/terraform.tfstate"
region       = "us-east-2"
encrypt      = true
use_lockfile = true
EOF

# 3. Inicializar e Aplicar a infraestrutura real
echo -e "${BLUE}3. Inicializando infraestrutura principal...${NC}"
terraform init -reconfigure -backend-config=backend.tfvars

echo -e "${BLUE}4. Aplicando mudanças na AWS...${NC}"
terraform apply -var-file=terraform.tfvars -auto-approve

echo -e "${GREEN}==== DEPLOY CONCLUÍDO COM SUCESSO! ====${NC}"
echo -e "${GREEN}IP da Instância:${NC} $(terraform output -raw instance_public_ip)"
