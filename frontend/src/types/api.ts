export interface SourceCitation {
  source: string
  filename: string
  heading_path?: string | null
  chunk_index?: number | null
}

export interface QueryRequest {
  question: string
  top_k?: number
}

export interface QueryResponse {
  answer: string
  sources: string[]
  citations?: SourceCitation[]
  chunks_used: number
}

export interface ChatRequest {
  session_id?: string
  message: string
  top_k?: number
}

export interface ChatResponse {
  session_id: string
  answer: string
  sources: string[]
  citations?: SourceCitation[]
  chunks_used: number
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatHistoryResponse {
  session_id: string
  messages: ChatMessage[]
}

export interface SessionClearResponse {
  session_id: string
  cleared: boolean
}

export interface UploadResponse {
  filename: string
  chunks_added: number
  sources: string[]
}

export interface IngestResponse {
  files_processed: number
  chunks_added: number
  skipped: string[]
}

export interface HealthResponse {
  status: string
  ollama_reachable: boolean
  qdrant_reachable: boolean
  chunk_count: number
  chat_model: string
  embed_model: string
  rerank_enabled: boolean
  rerank_model: string
  postgres_reachable: boolean
  agent_enabled?: boolean
  agent_model?: string | null
}

export interface ApiError {
  detail: string
}

export interface ChatStreamSessionEvent {
  session_id: string
}

export interface ChatStreamTokenEvent {
  text: string
}

export interface ChatStreamDoneEvent {
  session_id: string
  sources: string[]
  citations?: SourceCitation[]
  chunks_used: number
}

export interface ChatStreamErrorEvent {
  message: string
}

export type ChatStreamEvent =
  | { event: 'session'; data: ChatStreamSessionEvent }
  | { event: 'token'; data: ChatStreamTokenEvent }
  | { event: 'done'; data: ChatStreamDoneEvent }
  | { event: 'error'; data: ChatStreamErrorEvent }

export interface UiMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
  citations?: SourceCitation[]
  chunksUsed?: number
  error?: boolean
  streaming?: boolean
}

export interface UploadRecord {
  id: string
  filename: string
  chunksAdded: number
  sources: string[]
  uploadedAt: string
}

export interface AgentChatRequest {
  session_id?: string
  message: string
}

export interface AgentHistoryResponse {
  session_id: string
  messages: ChatMessage[]
}

export interface ToolStep {
  tool: string
  input?: Record<string, unknown>
  status: 'running' | 'done'
}

export interface ApprovalRequest {
  approval_id: string
  command: string
  reason?: string
}

export interface AgentStreamSessionEvent {
  session_id: string
  run_id: string
}

export interface AgentStreamTokenEvent {
  text: string
}

export interface AgentStreamToolEvent {
  tool: string
  input?: Record<string, unknown>
}

export interface AgentStreamDoneEvent {
  session_id: string
  run_id: string
  pending_approval?: ApprovalRequest | null
}

export interface PendingApprovalsResponse {
  approvals: ApprovalRequest[]
}

export interface ApprovalResponse {
  status: string
  approval_id: string
  result?: Record<string, unknown>
}

export type AgentStreamEvent =
  | { event: 'session'; data: AgentStreamSessionEvent }
  | { event: 'token'; data: AgentStreamTokenEvent }
  | { event: 'tool_start'; data: AgentStreamToolEvent }
  | { event: 'tool_end'; data: AgentStreamToolEvent & { duration_ms?: number; success?: boolean } }
  | { event: 'approval_required'; data: ApprovalRequest }
  | { event: 'done'; data: AgentStreamDoneEvent }
  | { event: 'error'; data: ChatStreamErrorEvent }

export interface AgentUiMessage extends UiMessage {
  toolSteps?: ToolStep[]
}
