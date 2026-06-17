import unittest
from types import SimpleNamespace

from fastapi import HTTPException

from app.routers.agent import _check_agent_auth


class AgentAuthTests(unittest.TestCase):
    @staticmethod
    def _request(*, agent_api_key: str, agent_require_api_key: bool):
        settings = SimpleNamespace(
            agent_api_key=agent_api_key,
            agent_require_api_key=agent_require_api_key,
        )
        app = SimpleNamespace(state=SimpleNamespace(settings=settings))
        return SimpleNamespace(app=app)

    def test_require_key_without_configuration_rejected(self) -> None:
        request = self._request(agent_api_key="", agent_require_api_key=True)
        with self.assertRaises(HTTPException) as ctx:
            _check_agent_auth(request, x_agent_key=None)
        self.assertEqual(ctx.exception.status_code, 503)

    def test_wrong_key_rejected(self) -> None:
        request = self._request(agent_api_key="secret", agent_require_api_key=True)
        with self.assertRaises(HTTPException) as ctx:
            _check_agent_auth(request, x_agent_key="bad")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_matching_key_allowed(self) -> None:
        request = self._request(agent_api_key="secret", agent_require_api_key=True)
        _check_agent_auth(request, x_agent_key="secret")


if __name__ == "__main__":
    unittest.main()
