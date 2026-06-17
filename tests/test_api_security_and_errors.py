import unittest
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.errors import install_exception_handlers
from app.observability import install_request_context_middleware
from app.security import install_public_api_key_middleware


class ApiSecurityAndErrorTests(unittest.TestCase):
    def _build_app(self, *, public_api_key: str = "") -> FastAPI:
        app = FastAPI()
        app.state.settings = SimpleNamespace(
            public_api_key=public_api_key,
            public_api_key_header="X-API-Key",
        )
        install_request_context_middleware(app)
        install_public_api_key_middleware(app)
        install_exception_handlers(app)

        @app.get("/query/ping")
        async def query_ping():
            return {"ok": True}

        @app.get("/boom")
        async def boom():
            raise RuntimeError("unexpected")

        @app.get("/http")
        async def http_error():
            raise HTTPException(status_code=400, detail="bad request")

        return app

    def test_public_api_key_required_for_protected_prefix(self) -> None:
        app = self._build_app(public_api_key="secret")
        client = TestClient(app)
        response = client.get("/query/ping")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "HTTP_UNAUTHORIZED")

    def test_public_api_key_allows_valid_header(self) -> None:
        app = self._build_app(public_api_key="secret")
        client = TestClient(app)
        response = client.get("/query/ping", headers={"X-API-Key": "secret"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

    def test_http_exception_uses_unified_payload(self) -> None:
        app = self._build_app()
        client = TestClient(app)
        response = client.get("/http")
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["message"], "bad request")

    def test_unhandled_exception_uses_unified_payload(self) -> None:
        app = self._build_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/boom")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"]["code"], "INTERNAL_SERVER_ERROR")


if __name__ == "__main__":
    unittest.main()
