from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.errors import error_payload

PROTECTED_PREFIXES = ("/query", "/chat", "/documents")


def install_public_api_key_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def public_api_key_guard(request: Request, call_next):
        settings = request.app.state.settings
        api_key = settings.public_api_key.strip()
        header_name = settings.public_api_key_header.strip()

        if (
            api_key
            and header_name
            and any(request.url.path.startswith(prefix) for prefix in PROTECTED_PREFIXES)
        ):
            header_value = request.headers.get(header_name)
            if header_value != api_key:
                return JSONResponse(
                    status_code=401,
                    content=error_payload(
                        code="HTTP_UNAUTHORIZED",
                        message=f"Invalid or missing {header_name}",
                    ),
                )

        return await call_next(request)
