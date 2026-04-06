import logging

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configurações globais da aplicação utilizando Pydantic Settings.
    Carrega valores de variáveis de ambiente ou do arquivo .env.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    stark_project_id: str
    stark_private_key: str
    stark_environment: str = "sandbox"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "payment_db"
    postgres_host: str = "db"
    postgres_port: int = 5432
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/payment_db"
    db_pooling: bool = True
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800
    redis_url: str = "redis://redis:6379/0"
    rabbitmq_url: str = "amqp://payment:payment@rabbitmq:5672/payment"
    celery_broker_url: str = "amqp://payment:payment@rabbitmq:5672/payment"
    celery_result_backend: str = "redis://redis:6379/0"
    worker_max_tasks_per_child: int = 1000
    webhook_max_retries: int = 10
    billing_max_retries: int = 5
    bootstrap_lock_ttl: int = 60
    debug: bool = False
    log_level: str = "INFO"
    log_sensitive_keywords: set[str] = {
        "tax_id",
        "cpf",
        "cnpj",
        "stark_private_key",
        "private_key",
        "password",
        "secret",
        "token",
        "digital_signature",
        "name",
        "email",
        "phone",
        "account_number",
        "branch_code",
    }
    otel_enabled: bool = False
    otel_endpoint: str = "http://otel-collector:4317"
    otel_export_timeout: int = 10
    otel_batch_max_queue_size: int = 2048
    otel_batch_export_size: int = 512
    otel_batch_delay_ms: int = 5000
    generate_invoices_enabled: bool = True
    batch_size_min: int = 8
    batch_size_max: int = 12
    batch_amount_min: int = 1000
    batch_amount_max: int = 100000
    batch_interval_minutes: int = 0
    batch_interval_hours: int = 3
    lifecycle_hours: int = 24
    invoice_due_hours: int = 24
    sandbox_tax_id: str = "20.018.183/0001-80"
    sandbox_bank_code: str = "20018183"
    sandbox_branch_code: str = "0001"
    sandbox_account_number: str = "6341320293482496"
    sandbox_account_type: str = "payment"


settings = Settings()
logging.getLogger("payment-orchestrator").info(
    f"CONFIG: generate_invoices_enabled={settings.generate_invoices_enabled}"
)
