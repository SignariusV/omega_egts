"""EventBus — асинхронная шина событий с ordered/parallel обработчиками."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Событие с именем и данными."""

    name: str
    data: dict[str, Any] = field(default_factory=dict)


HandlerType = Callable[[dict[str, Any]], Any]


class EventBus:
    """Асинхронная шина событий с поддержкой ordered и parallel обработчиков.

    Ordered-обработчики выполняются последовательно, в порядке регистрации.
    Parallel-обработчики выполняются параллельно через asyncio.gather.
    Ordered всегда завершаются до начала выполнения parallel.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[HandlerType]] = {}
        self._ordered_handlers: dict[str, list[HandlerType]] = {}

    def on(self, event_name: str, handler: HandlerType, ordered: bool = False) -> None:
        """Подписаться на событие.

        Args:
            event_name: Имя события (например, ``"packet.processed"``).
            handler: Вызываемый обработчик (синхронный или асинхронный).
            ordered: Если ``True``, обработчик выполняется последовательно
                до всех parallel-обработчиков.
        """
        if ordered:
            self._ordered_handlers.setdefault(event_name, []).append(handler)
        else:
            self._handlers.setdefault(event_name, []).append(handler)

    def off(self, event_name: str, handler: HandlerType) -> None:
        """Отписаться от события.

        Args:
            event_name: Имя события.
            handler: Обработчик для удаления.
        """
        for handler_list in (self._handlers, self._ordered_handlers):
            target = handler_list.get(event_name, [])
            if handler in target:
                target.remove(handler)

    async def emit(self, event_name: str, data: dict[str, Any]) -> None:
        """Опубликовать событие.

        Сначала последовательно выполняются все ordered-обработчики,
        затем параллельно — все parallel-обработчики через ``asyncio.gather``.
        Ошибка в одном parallel-обработчике не прерывает остальные.

        Args:
            event_name: Имя события для публикации.
            data: Данные события, передаваемые всем обработчикам.
        """
        # 1. Ordered — строго последовательно
        for handler in self._ordered_handlers.get(event_name, []):
            await self._invoke_handler(handler, data)

        # 2. Parallel — параллельно через asyncio.gather
        parallel_tasks: list[asyncio.Task[None]] = []
        for handler in self._handlers.get(event_name, []):
            task = asyncio.create_task(self._invoke_handler(handler, data))
            parallel_tasks.append(task)

        if parallel_tasks:
            await asyncio.gather(*parallel_tasks, return_exceptions=True)

    @staticmethod
    async def _invoke_handler(handler: HandlerType, data: dict[str, Any]) -> None:
        """Вызвать обработчик, поддерживая и sync, и async функции."""
        if asyncio.iscoroutinefunction(handler):
            await handler(data)
        else:
            handler(data)
