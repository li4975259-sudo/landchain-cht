from pydantic import BaseModel, Field


class SourceCitation(BaseModel):
    source: str
    filename: str
    heading_path: str | None = None
    chunk_index: int | None = None


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="用户问题")
    top_k: int | None = Field(default=None, ge=1, le=20, description="检索 chunk 数量")


class QueryResponse(BaseModel):
    answer: str
    sources: list[str]
    citations: list[SourceCitation] = Field(default_factory=list)
    chunks_used: int
    mode: str = Field(default="rag", description="rag=知识库检索, chitchat=直连模型闲聊")


class ChatRequest(BaseModel):
    session_id: str | None = Field(default=None, description="会话 ID，不传则自动生成")
    message: str = Field(..., min_length=1, description="用户消息")
    top_k: int | None = Field(default=None, ge=1, le=20, description="检索 chunk 数量")


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sources: list[str]
    citations: list[SourceCitation] = Field(default_factory=list)
    chunks_used: int
    mode: str = Field(default="rag", description="rag=知识库检索, chitchat=直连模型闲聊")


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: list[dict]


class SessionClearResponse(BaseModel):
    session_id: str
    cleared: bool


class UploadResponse(BaseModel):
    filename: str
    chunks_added: int
    sources: list[str]


class IngestResponse(BaseModel):
    files_processed: int
    chunks_added: int
    skipped: list[str]


class HealthResponse(BaseModel):
    status: str
    ollama_reachable: bool
    qdrant_reachable: bool
    chunk_count: int
    chat_model: str
    embed_model: str
    rerank_enabled: bool
    rerank_model: str
    postgres_reachable: bool
    agent_enabled: bool = False
    agent_model: str | None = None


class AgentChatRequest(BaseModel):
    session_id: str | None = None
    message: str = Field(..., min_length=1)


class AgentChatResponse(BaseModel):
    session_id: str
    run_id: str
    answer: str
    pending_approval: dict | None = None


class AgentHistoryResponse(BaseModel):
    session_id: str
    messages: list[dict]


class AgentRunsResponse(BaseModel):
    session_id: str
    runs: list[dict]


class ApprovalActionRequest(BaseModel):
    resolved_by: str = "user"


class ApprovalResponse(BaseModel):
    status: str
    approval_id: str
    result: dict | None = None


class PendingApprovalsResponse(BaseModel):
    approvals: list[dict]


class AgentToolsResponse(BaseModel):
    tools: list[dict]

