from dataclasses import dataclass

from app.domain.exceptions import DomainException


@dataclass(frozen=True)
class Money:
    """
    Value Object representando valores monetários em centavos.
    Garante precisão decimal e imutabilidade.
    """
    amount: int
    currency: str = "BRL"

    def __post_init__(self):
        if self.amount < 0:
            raise DomainException("Valor monetário não pode ser negativo")

    def __add__(self, other: 'Money') -> 'Money':
        if self.currency != other.currency:
            raise DomainException("Não é possível somar moedas diferentes")
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: 'Money') -> 'Money':
        if self.currency != other.currency:
            raise DomainException("Não é possível subtrair moedas diferentes")
        if self.amount < other.amount:
            raise DomainException("Saldo insuficiente para a operação")
        return Money(self.amount - other.amount, self.currency)

    def __str__(self) -> str:
        return f"{self.currency} {self.amount / 100:.2f}"
