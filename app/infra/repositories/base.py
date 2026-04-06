from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

class SqlAlchemyRepository:

    def __init__(self, session: AsyncSession):
        self.session = session
