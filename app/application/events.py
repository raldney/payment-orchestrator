import asyncio
import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger('payment-orchestrator.events')

@dataclass
class DomainEvent:
    pass

class EventDispatcher:

    def __init__(self):
        self._handlers: dict[type[DomainEvent], list[Callable]] = {}

    def subscribe(self, event_type: type[DomainEvent], handler: Callable):
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f'Subscribed {handler.__name__} to {event_type.__name__}')

    def dispatch(self, event: DomainEvent):
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    asyncio.create_task(handler(event))
                else:
                    handler(event)
            except Exception as e:
                logger.error(f'Error in event handler {handler.__name__} for {event_type.__name__}: {e}')
dispatcher = EventDispatcher()
