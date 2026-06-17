import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.observability import REQUEST_ID_HEADER, install_request_context_middleware


class ObservabilityTests(unittest.TestCase):
    def test_preserves_incoming_request_id_header(self) -> None:
        app = FastAPI()
        install_request_context_middleware(app)

        @app.get("/ping")
        async def ping():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/ping", headers={REQUEST_ID_HEADER: "rid-123"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get(REQUEST_ID_HEADER), "rid-123")

    def test_generates_request_id_when_missing(self) -> None:
        app = FastAPI()
        install_request_context_middleware(app)

        @app.get("/ping")
        async def ping():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/ping")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers.get(REQUEST_ID_HEADER))


if __name__ == "__main__":
    unittest.main()
