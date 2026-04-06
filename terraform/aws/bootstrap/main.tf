provider "aws" {
  region = "us-east-2"
}

# Gera um ID aleatório para garantir que o nome do bucket seja único no mundo
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

locals {
  # Nome padrão que dificilmente vai colidir
  bucket_name = "payment-orchestrator-state-${random_id.bucket_suffix.hex}"
}

# --- Bucket S3 para o Estado ---
resource "aws_s3_bucket" "terraform_state" {
  bucket        = local.bucket_name
  force_destroy = false

  tags = {
    Name        = "Terraform State Storage"
    Environment = "Management"
  }
}

# Habilitar Versionamento
resource "aws_s3_bucket_versioning" "enabled" {
  bucket = aws_s3_bucket.terraform_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Bloquear acesso público
resource "aws_s3_bucket_public_access_block" "public_access" {
  bucket                  = aws_s3_bucket.terraform_state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Printa o nome gerado para você colocar no seu backend.tfvars
output "s3_bucket_name" {
  value = aws_s3_bucket.terraform_state.id
  description = "COPIE ESTE NOME para o seu arquivo backend.tfvars"
}
