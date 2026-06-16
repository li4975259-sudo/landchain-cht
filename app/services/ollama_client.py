import httpx

from app.config import Settings, get_settings
from langchain_ollama import ChatOllama, OllamaEmbeddings


def create_chat_model(settings: Settings | None = None) -> ChatOllama:
    settings = settings or get_settings()
    return ChatOllama(
        model=settings.ollama_chat_model,
        base_url=settings.ollama_base_url,
        temperature=0.2,
    )


def create_agent_model(settings: Settings | None = None) -> ChatOllama:
    settings = settings or get_settings()
    return ChatOllama(
        model=settings.effective_agent_model,
        base_url=settings.ollama_base_url,
        temperature=0.2,
    )


def create_embeddings(settings: Settings | None = None) -> OllamaEmbeddings:
    settings = settings or get_settings()
    return OllamaEmbeddings(
        model=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )


async def check_ollama_health(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            return response.status_code == 200
    except httpx.HTTPError:
        return False
