from abc import ABC, abstractmethod

from app.domain.entities.transfer import Transfer


class TransferGateway(ABC):

    @abstractmethod
    async def execute_transfer(self, transfer: Transfer) -> Transfer:
        pass
