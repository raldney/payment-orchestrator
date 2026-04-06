from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.exceptions import DomainException
from app.infra.adapters.starkbank_adapter.client import init_starkbank
from app.infra.api.v1.billing import router as billing_router
from app.infra.api.v1.transfers import router as transfers_router
from app.infra.api.v1.webhooks import router as webhook_router
from app.infra.config import settings
from app.infra.observability import instrument_app, logger, setup_metrics, setup_tracing


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Initializing StarkBank SDK and Observability...")
    setup_tracing()
    setup_metrics()
    init_starkbank()
    yield


app = FastAPI(
    title="StarkBank Payment Orchestrator",
    description="Automação de Faturas e Transferências (Stark Bank Sandbox)",
    version="1.0.0",
    lifespan=lifespan,
)
instrument_app(app)
app.include_router(webhook_router)
app.include_router(billing_router)
app.include_router(transfers_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@app.exception_handler(DomainException)
async def domain_exception_handler(
    request: Request, exc: DomainException
) -> JSONResponse:
    logger.error(f"Domain Rule Validation Failed: {exc.message}")
    return JSONResponse(
        status_code=422,
        content={"error": "DomainValidationFailed", "message": exc.message},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.app_host, port=settings.app_port)
