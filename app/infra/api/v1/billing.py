from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.events import dispatcher
from app.application.use_cases.generate_invoices import GenerateInvoiceBatchUseCase
from app.infra.api.dependencies import get_generate_invoices_usecase
from app.infra.config import settings
from app.infra.database import get_db
from app.infra.observability import logger
from app.infra.repositories.payment_repo import PaymentRepository

router = APIRouter(prefix="/v1/billing", tags=["billing"])


@router.post("/generate-batch")
async def trigger_manual_invoice_generation(
    count: int | None = None,
    session: AsyncSession = Depends(get_db),
    use_case: GenerateInvoiceBatchUseCase = Depends(get_generate_invoices_usecase),
):
    try:
        invoices, event = await use_case.execute(count=count)
        await session.commit()
        dispatcher.dispatch(event)
        return {
            "status": "success",
            "count": len(invoices),
            "invoices": [{"id": i.id, "amount": i.amount} for i in invoices],
        }
    except Exception as e:
        await session.rollback()
        logger.error(f"Manual generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/invoices")
async def list_invoices(
    limit: int = 50, offset: int = 0, session: AsyncSession = Depends(get_db)
):
    repo = PaymentRepository(session)
    invoices = await repo.list_invoices(limit=limit, offset=offset)
    return {"count": len(invoices), "invoices": invoices}


@router.get("/invoices/{invoice_id}")
async def get_invoice_details(invoice_id: str, session: AsyncSession = Depends(get_db)):
    repo = PaymentRepository(session)
    invoice = await repo.get_invoice_by_id(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.get("/schedule")
async def get_next_schedule():
    now = datetime.now(UTC)
    interval = settings.batch_interval_hours
    current_hour = now.hour
    next_hour = (current_hour // interval + 1) * interval
    next_run = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
        hours=next_hour
    )
    time_remaining = next_run - now
    return {
        "next_execution_at": next_run.isoformat(),
        "interval_hours": interval,
        "seconds_remaining": int(time_remaining.total_seconds()),
        "human_readable_remaining": str(time_remaining).split(".")[0],
        "cron_expression": f"0 */{interval} * * *",
    }
