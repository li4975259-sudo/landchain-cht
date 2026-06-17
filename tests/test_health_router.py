import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.routers.health import health


class _VectorStoreStub:
    def __init__(self, *, ping_ok: bool, count: int) -> None:
        self._ping_ok = ping_ok
        self._count = count

    def ping(self) -> bool:
        return self._ping_ok

    def count(self) -> int:
        return self._count


class _BusinessStoreStub:
    def __init__(self, *, ping_ok: bool) -> None:
        self._ping_ok = ping_ok

    def ping(self) -> bool:
        return self._ping_ok


class HealthRouterTests(unittest.TestCase):
    def _request(self, *, vector_ping: bool, postgres_ping: bool):
        settings = SimpleNamespace(
            ollama_chat_model="chat-model",
            embed_model="embed-model",
            rerank_enabled=True,
            rerank_model="rerank-model",
            agent_enabled=True,
            effective_agent_model="agent-model",
        )
        app_state = SimpleNamespace(
            settings=settings,
            vectorstore=_VectorStoreStub(ping_ok=vector_ping, count=9),
            business_store=_BusinessStoreStub(ping_ok=postgres_ping),
        )
        return SimpleNamespace(app=SimpleNamespace(state=app_state))

    def test_health_returns_ok_when_all_dependencies_up(self) -> None:
        request = self._request(vector_ping=True, postgres_ping=True)
        with patch("app.routers.health.check_ollama_health", new=AsyncMock(return_value=True)):
            response = asyncio.run(health(request))
        self.assertEqual(response.status, "ok")
        self.assertTrue(response.agent_enabled)
        self.assertEqual(response.chunk_count, 9)

    def test_health_returns_degraded_when_dependency_down(self) -> None:
        request = self._request(vector_ping=False, postgres_ping=True)
        with patch("app.routers.health.check_ollama_health", new=AsyncMock(return_value=True)):
            response = asyncio.run(health(request))
        self.assertEqual(response.status, "degraded")
        self.assertFalse(response.qdrant_reachable)


if __name__ == "__main__":
    unittest.main()
