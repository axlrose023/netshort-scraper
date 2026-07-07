from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable, Iterable


async def _aiter[T](items: Iterable[T] | AsyncIterable[T]) -> AsyncIterator[T]:
    if isinstance(items, AsyncIterable):
        async for item in items:
            yield item
        return

    for item in items:
        yield item


async def map_bounded[T, R](
    items: Iterable[T] | AsyncIterable[T],
    coro_fn: Callable[[T], Awaitable[R]],
    *,
    limit: int,
) -> AsyncIterator[R]:
    if limit < 1:
        raise ValueError("limit must be >= 1")

    iterator = _aiter(items)
    pending: set[asyncio.Task[R]] = set()
    exhausted = False

    async def _run(item: T) -> R:
        return await coro_fn(item)

    async def _refill() -> None:
        nonlocal exhausted
        while len(pending) < limit:
            if exhausted:
                return
            try:
                item = await anext(iterator)
            except StopAsyncIteration:
                exhausted = True
                return
            pending.add(asyncio.create_task(_run(item)))

    try:
        await _refill()
        while pending:
            done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                pending.discard(task)
                yield task.result()
            await _refill()
    finally:
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
