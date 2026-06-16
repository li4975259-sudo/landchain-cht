from contextlib import asynccontextmanager



import logging

from dotenv import load_dotenv

from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware



from app.agents.agent_service import AgentService

from app.config import get_settings

from app.routers import agent, chat, documents, health, query

from app.services.chat_graph import ChatGraphService

from app.services.chunk_expand import ChunkExpandService

from app.services.embeddings import create_embedding_service

from app.services.hybrid_retrieval import HybridRetrievalService

from app.services.ingest import IngestService

from app.services.ollama_client import create_agent_model, create_chat_model

from app.services.postgres_business_store import PostgresBusinessStore

from app.services.query_rewrite import QueryRewriteService

from app.services.rag import RagService

from app.services.rerank import RerankService

from app.services.retrieval import RetrievalService

from app.services.vectorstore import VectorStoreService



load_dotenv()



logger = logging.getLogger(__name__)





@asynccontextmanager

async def lifespan(app: FastAPI):

    settings = get_settings()

    embeddings = create_embedding_service(settings)

    vectorstore = VectorStoreService(embeddings, settings)

    vectorstore.ensure_collection()

    business_store = PostgresBusinessStore(settings)

    ingest_service = IngestService(vectorstore, settings)

    rerank_service = RerankService(settings)

    query_rewrite_service = QueryRewriteService(settings=settings)

    hybrid_retrieval_service = HybridRetrievalService(vectorstore, settings)

    chunk_expand_service = ChunkExpandService(vectorstore, settings)

    retrieval_service = RetrievalService(

        vectorstore,

        rerank_service,

        query_rewrite_service=query_rewrite_service,

        hybrid_retrieval_service=hybrid_retrieval_service,

        chunk_expand_service=chunk_expand_service,

        settings=settings,

    )

    llm = create_chat_model(settings)

    rag_service = RagService(retrieval_service, llm, settings)

    chat_service = ChatGraphService(retrieval_service, llm, settings)



    agent_service = None

    if settings.agent_enabled:

        agent_llm = create_agent_model(settings)

        agent_service = AgentService(

            retrieval_service, business_store, ingest_service, agent_llm, settings

        )



    app.state.settings = settings

    app.state.vectorstore = vectorstore

    app.state.business_store = business_store

    app.state.ingest_service = ingest_service

    app.state.rag_service = rag_service

    app.state.chat_service = chat_service

    app.state.agent_service = agent_service



    try:

        files_processed, chunks_added, skipped = ingest_service.ingest_directory()

        logger.info(

            "Startup ingest complete: files=%s chunks=%s skipped=%s",

            files_processed,

            chunks_added,

            skipped,

        )

    except Exception:

        logger.exception("Startup ingest failed")



    yield





def create_app() -> FastAPI:

    settings = get_settings()

    app = FastAPI(

        title="LandChain RAG API",

        description="RAG service powered by LangChain, FastAPI, and local Ollama",

        version="0.6.0",

        lifespan=lifespan,

    )

    app.add_middleware(

        CORSMiddleware,

        allow_origins=settings.cors_origin_list,

        allow_credentials=True,

        allow_methods=["*"],

        allow_headers=["*"],

    )

    app.include_router(health.router)

    app.include_router(query.router)

    app.include_router(chat.router)

    app.include_router(documents.router)

    app.include_router(agent.router)

    return app





app = create_app()

