class DomainException(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class GatewayUnavailableError(DomainException):
    pass


class ValidationFailedError(DomainException):
    pass


class EntityNotFoundError(DomainException):
    pass
