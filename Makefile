.PHONY: help setup keys test lint infra-init infra-plan infra-apply deploy dev docs docs-build clean reset

# Cores para o terminal
BLUE = \033[0;34m
GREEN = \033[0;32m
YELLOW = \033[1;33m
NC = \033[0m

help: ## Exibe esta ajuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Instala dependências locais e configura o .env
	@echo "$(BLUE)Instalando dependências com uv...$(NC)"
	uv sync
	@if [ ! -f .env ]; then cp .env.example .env; echo "$(GREEN).env criado a partir do exemplo.$(NC)"; fi

keys: ## Gera chaves ECDSA para o StarkBank
	@uv run python scripts/generate_keys.py

lint: ## Executa checagem de estilo e tipos (Ruff + Mypy)
	@echo "$(BLUE)Rodando Ruff...$(NC)"
	uv run ruff check .
	@echo "$(BLUE)Rodando Mypy...$(NC)"
	uv run mypy .

test: ## Executa todos os testes unitários e de integração
	@echo "$(BLUE)Executando testes...$(NC)"
	uv run pytest

dev: ## Sobe o ambiente de desenvolvimento local (Docker Compose)
	@echo "$(BLUE)Subindo ambiente local...$(NC)"
	docker compose up -d --build

docs: ## Inicia o servidor de documentação (MkDocs)
	@echo "$(BLUE)Iniciando MkDocs...$(NC)"
	uv run --group docs mkdocs serve

docs-build: ## Gera a versão estática da documentação
	@echo "$(BLUE)Gerando documentação estática...$(NC)"
	uv run --group docs mkdocs build

infra-init: ## Inicializa o Terraform AWS (Bootstrap)
	@echo "$(BLUE)Inicializando Bootstrap AWS...$(NC)"
	cd terraform/aws/bootstrap && terraform init
	@echo "$(BLUE)Inicializando Infra Principal AWS...$(NC)"
	cd terraform/aws && terraform init -backend-config=backend.tfvars

infra-plan: ## Mostra o plano de execução do Terraform AWS
	@echo "$(YELLOW)Planejando infraestrutura...$(NC)"
	cd terraform/aws && terraform plan -var-file=terraform.tfvars

infra-apply: ## Aplica as mudanças do Terraform na AWS
	@echo "$(GREEN)Aplicando infraestrutura...$(NC)"
	cd terraform/aws && terraform apply -var-file=terraform.tfvars -auto-approve

deploy: ## Executa o deploy completo para a AWS via ship-it.sh
	@echo "$(GREEN)🚀 Iniciando Deploy para AWS...$(NC)"
	chmod +x ship-it.sh
	./ship-it.sh

reset: ## Executa o deploy com HARD RESET (apaga volumes remotos)
	@echo "$(YELLOW)⚠️  Iniciando Deploy com RESET TOTAL...$(NC)"
	chmod +x ship-it.sh
	./ship-it.sh --reset

clean: ## Limpa arquivos temporários, caches do Python, Celery e ferramentas
	@echo "$(BLUE)Limpando caches e arquivos temporários...$(NC)"
	@rm -rf .pytest_cache .ruff_cache .mypy_cache
	@rm -rf .coverage htmlcov/ coverage.xml
	@rm -rf celerybeat-schedule celerybeat.pid
	@rm -rf build/ dist/ *.egg-info/
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type f -name "*.py[co]" -delete
	@find . -type f -name "*.pyd" -delete
	@find . -type f -name ".DS_Store" -delete
	@echo "$(GREEN)Limpeza de cache concluída com sucesso!$(NC)"

clean-all: clean ## Limpa TUDO, incluindo .venv e ferramentas extras
	@echo "$(YELLOW)Removendo ambiente virtual (.venv)...$(NC)"
	@rm -rf .venv
	@echo "$(YELLOW)Derrubando containers do Docker...$(NC)"
	@docker compose down -v --remove-orphans
	@echo "$(GREEN)Limpeza profunda do projeto feita!$(NC)"
