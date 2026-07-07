from __future__ import annotations

import asyncio

import pytest

from scraper.core.concurrency import map_bounded


class TestMapBounded:
    async def test_yields_all_results(self):
        async def double(x: int) -> int:
            return x * 2

        got = sorted([r async for r in map_bounded(range(10), double, limit=3)])
        assert got == [x * 2 for x in range(10)]

    async def test_never_exceeds_limit_in_flight(self):
        active = 0
        peak = 0

        async def work(x: int) -> int:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1
            return x

        _ = [r async for r in map_bounded(range(20), work, limit=4)]
        assert peak <= 4

    async def test_empty_input(self):
        async def work(x: int) -> int:
            return x

        assert [r async for r in map_bounded([], work, limit=3)] == []

    async def test_accepts_async_iterable_without_preloading(self):
        produced = 0
        peak_buffer = 0

        async def source():
            nonlocal produced, peak_buffer
            for x in range(10):
                produced += 1
                peak_buffer = max(peak_buffer, produced)
                yield x

        async def work(x: int) -> int:
            nonlocal produced
            await asyncio.sleep(0.01)
            produced -= 1
            return x

        got = sorted([r async for r in map_bounded(source(), work, limit=3)])

        assert got == list(range(10))
        assert peak_buffer <= 3

    async def test_invalid_limit_rejected(self):
        async def work(x: int) -> int:
            return x

        with pytest.raises(ValueError, match="limit"):
            _ = [r async for r in map_bounded([1], work, limit=0)]

    async def test_early_close_cancels_pending(self):
        cancelled: list[int] = []

        async def work(x: int) -> int:
            try:
                await asyncio.sleep(0 if x == 0 else 10)
            except asyncio.CancelledError:
                cancelled.append(x)
                raise
            return x

        gen = map_bounded(range(5), work, limit=5)
        async for r in gen:
            assert r == 0  # only the instant task completes before we bail
            break
        await gen.aclose()  # triggers the finally → the 10s tasks are cancelled

        assert set(cancelled) == {1, 2, 3, 4}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
