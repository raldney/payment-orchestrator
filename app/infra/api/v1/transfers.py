from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import get_db
from app.infra.repositories.payment_repo import PaymentRepository

router = APIRouter(prefix='/v1/transfers', tags=['transfers'])

@router.get('/')
async def list_transfers(limit: int=50, offset: int=0, session: AsyncSession=Depends(get_db)):
    repo = PaymentRepository(session)
    transfers = await repo.list_transfers(limit=limit, offset=offset)
    return {'count': len(transfers), 'transfers': transfers}
