import asyncio
import unittest

from app.utils.async_bridge import iter_sync_in_thread, run_sync


class AsyncBridgeTests(unittest.TestCase):
    def test_run_sync_executes_blocking_call(self) -> None:
        async def _run():
            return await run_sync(lambda x, y: x + y, 2, 3)

        result = asyncio.run(_run())
        self.assertEqual(result, 5)

    def test_iter_sync_in_thread_streams_values(self) -> None:
        async def _collect():
            values: list[int] = []
            async for item in iter_sync_in_thread(iter([1, 2, 3])):
                values.append(item)
            return values

        result = asyncio.run(_collect())
        self.assertEqual(result, [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
