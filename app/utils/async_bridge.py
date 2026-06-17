from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Iterator
from typing import cast
from typing import TypeVar

T = TypeVar("T")


async def run_sync(func: Callable[..., T], /, *args, **kwargs) -> T:
    return await asyncio.to_thread(func, *args, **kwargs)


def _next_item(iterator: Iterator[T]) -> tuple[bool, T | None]:
    try:
        return False, next(iterator)
    except StopIteration:
        return True, None


async def iter_sync_in_thread(iterator: Iterator[T]) -> AsyncIterator[T]:
    while True:
        done, item = await asyncio.to_thread(_next_item, iterator)
        if done:
            break
        yield cast(T, item)
