# LandChain Agent 能力说明

LandChain 超级智能体通过 LangGraph ReAct 循环调用工具，主要能力：

- **RAG 知识库**：`search_knowledge_base`、`list_knowledge_sources`、`ingest_documents`
- **PostgreSQL 业务数据**：`explore_data` + `query_data`（Schema-on-Read）
- **报告生成**：`generate_order_report`、`generate_markdown_report`
- **任务脚本**：`list_tasks`、`run_task`（如 daily_orders、daily_uv）
- **运维**：`get_system_health`、`run_shell_command`（需用户审批）

## 数据路由

| 问题类型 | 推荐工具 |
|---------|---------|
| 文档/政策/已入库内容 | `search_knowledge_base` |
| 实时业务 JSON 数据 | `explore_data` → `query_data` |
| 订单统计报告 | `generate_order_report` |
| 自定义汇总文档 | `generate_markdown_report` |

## 环境要求

- Agent 依赖 PostgreSQL 业务库与 Qdrant 向量库均可用
- 会话与审计使用 SQLite（`agent_sessions.db`、`agent_audit.db`）
