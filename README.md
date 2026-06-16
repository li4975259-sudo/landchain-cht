# LandChain RAG API

基于 **LangChain + FastAPI + 本地 Ollama** 的 RAG（检索增强生成）HTTP 服务。

## 功能

- 本地 Ollama 完成 embedding 与对话生成
- 启动时自动增量导入 `data/` 目录文档
- HTTP 上传 PDF / TXT / Markdown
- 问答接口支持 JSON 一次性返回与 SSE 流式输出
- **Cross-Encoder 重排序**：向量检索后二次精排，提升召回精度
- **LangGraph 多轮对话**：基于 SQLite 持久化 session memory
- **Qdrant** 向量库（向量 + chunk 原文 payload 统一存储），重启无需重新 embedding
- **PostgreSQL 订单 → 统计 Markdown → RAG**：CLI 按 `created_at` 区间从 PostgreSQL 聚合订单，生成 `data/orders/` 报告并文本切分入库

## 前置条件

1. 安装 [Ollama](https://ollama.com/) 并确保服务运行中
2. Python 3.10+
3. 拉取模型：

```bash
ollama pull gpt-oss:120b-cloud
ollama pull nomic-embed-text
```

验证 Ollama：

```bash
curl http://localhost:11434/api/tags
```

## 快速开始

```bash
# 创建虚拟环境
python -m venv .venv

# Windows
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
copy .env.example .env

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动后访问 API 文档：http://localhost:8000/docs

## Docker Compose 部署（Ollama 仍用本机）

仅容器化 **FastAPI API**，**Ollama 继续在宿主机运行**（Windows 本机或 WSL 均可）。

### 前置条件

1. 安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)
2. 本机 Ollama 已启动，并已拉取模型：

```bash
ollama pull gpt-oss:120b-cloud
ollama pull nomic-embed-text
```

3. 确认宿主机可访问 Ollama：

```powershell
Invoke-RestMethod http://localhost:11434/api/tags
```

### 一键启动

```powershell
cd e:\work\landchain

# 首次：复制环境变量（若尚未配置）
copy .env.example .env

# 构建并启动（API :8000，前端 :3000）
docker compose up -d --build
```

访问：

- 前端控制台：http://localhost:3000
- API 文档：http://localhost:8000/docs

查看日志：

```powershell
docker compose logs -f
docker compose logs -f frontend
docker compose logs -f api
```

停止服务：

```powershell
docker compose down
```

### 说明

| 项目 | 行为 |
|------|------|
| 前端 | Nginx 静态站点 `:3000`，`/api` 反向代理到 `api:8000` |
| Qdrant | 容器 `landchain-qdrant`，端口 `:6333`，数据卷 `qdrant_data` |
| PostgreSQL | 容器 `landchain-postgres`，端口 `:5432`，数据卷 `postgres_data` |
| Ollama | 宿主机 `localhost:11434`，API 容器通过 `host.docker.internal` 访问 |
| 文档目录 | `./data` 挂载到容器，与本地开发共用 |
| 会话/上传 | `./storage` 挂载到容器（SQLite 会话、上传文件、HF 缓存） |
| 重排模型缓存 | `./storage/hf_cache`，避免每次重建容器重新下载 |

**注意：**

- 若本机已用 `uvicorn` 占用 8000 端口，需先停止再 `docker compose up`
- `.env` 里 `OLLAMA_BASE_URL=localhost` 仅适用于本机直跑；Compose 会自动覆盖为 `host.docker.internal`
- 首次启动镜像构建较慢（含 PyTorch + sentence-transformers）

### Qdrant

Compose 已包含 Qdrant。**向量与 chunk 原文统一存储在 Qdrant payload 中**，无需双库同步。

```
导入文档 → 切分 chunk → Qdrant（embedding + content + metadata payload）
检索时：Qdrant 相似度搜索 → 直接返回正文 → Cross-Encoder 重排
```

默认 collection：`landchain_rag`（768 维 COSINE，配合 `nomic-embed-text`）。

仅启动 Qdrant：

```powershell
docker compose up -d qdrant
```

验证：

```powershell
Invoke-RestMethod http://localhost:6333/collections
```

本机直跑 API 时 `.env` 使用 `QDRANT_URL=http://localhost:6333`；API 在 Docker 内时 compose 自动设为 `http://qdrant:6333`。

向量数据持久化在 Docker 卷 `qdrant_data`。

**从旧版 Milvus/Mongo 迁移后需重新导入文档**：

```powershell
docker compose exec api python scripts/ingest_data.py --force
```

### PostgreSQL

Compose 已包含 PostgreSQL 16。业务 JSON（如 `order` 订单）存储在 `business_records` 表（JSONB），供 Agent 与统计脚本读取。

默认账号见 `.env.example`：

| 变量 | 默认值 |
|------|--------|
| `POSTGRES_USER` | `landchain` |
| `POSTGRES_PASSWORD` | `landchain` |
| `POSTGRES_DB` | `landchain` |

仅启动 PostgreSQL：

```powershell
docker compose up -d postgres
```

验证：

```powershell
docker exec landchain-postgres pg_isready -U landchain -d landchain
```

### PostgreSQL 订单 → 统计 Markdown → RAG

业务订单先写入 PostgreSQL 业务集合（默认 `order`），再通过 CLI 按 `created_at` 时间区间聚合统计，生成 Markdown 报告到 `data/orders/`，最后走与手工文档相同的文本切分（800/120）入库 RAG。

```bash
# 1. 写入测试订单（可选）
python scripts/seed_order_test_data.py --count 1000

# 2. 按时间区间生成报告并 ingest
python scripts/sync_orders_to_rag.py \
  --from 2025-01-01T00:00:00Z \
  --to 2026-06-30T23:59:59Z

# 只生成 Markdown、不入库
python scripts/sync_orders_to_rag.py --from ... --to ... --generate-only

# 只 ingest 已有报告
python scripts/sync_orders_to_rag.py --ingest-only --file data/orders/order-report_2025-01-01_2026-06-30.md

# 预览匹配数量
python scripts/sync_orders_to_rag.py --from ... --to ... --dry-run
```

Docker 内：

```powershell
docker compose exec api python scripts/sync_orders_to_rag.py --from 2025-01-01T00:00:00Z --to 2026-06-30T23:59:59Z
```

生成的报告包含：汇总 KPI、月度明细、分品牌/渠道/区域统计、订单明细台账。RAG `source` 为报告文件的绝对路径。

**说明**：迁移架构后需 `--force` 全量 re-ingest 知识库文档。

## 项目结构

```
landchain/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── config.py              # 配置
│   ├── models/schemas.py    # 请求/响应模型
│   ├── services/
│   │   ├── retrieval.py     # 向量检索 + Cross-Encoder 重排
│   │   ├── rerank.py        # Cross-Encoder 精排
│   │   ├── chat_graph.py    # LangGraph 多轮对话 + session memory
│   │   ├── postgres_business_store.py  # 业务 JSON 集合读写
│   │   ├── vectorstore.py              # Qdrant 向量操作
│   │   ├── order_report.py    # 订单统计 → Markdown 报告
│   │   └── ...              # RAG、向量库、导入逻辑
│   └── routers/             # HTTP 路由
├── frontend/                # React 聊天控制台（Vite）
├── data/                    # 预置文档目录
├── storage/                 # 向量库与上传文件（自动生成）
├── Dockerfile               # API 镜像
├── docker-compose.yml       # API + 前端一键部署
├── frontend/
│   ├── Dockerfile           # 前端镜像（Vite build + Nginx）
│   └── nginx.conf           # /api 反代 + SPA 路由
└── scripts/
    ├── ingest_data.py       # CLI 手动导入 data/
    ├── seed_order_test_data.py  # 写入测试订单到 PostgreSQL
    └── sync_orders_to_rag.py    # 订单统计报告生成 + RAG ingest
```

## API 接口

### GET /health

健康检查，返回 Ollama、Qdrant、PostgreSQL 连通性与 chunk 数量。

```bash
curl http://localhost:8000/health
```

### POST /documents/upload

上传文档（multipart/form-data，字段 `file`）。

```bash
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@data/sample.md"
```

### POST /documents/ingest

手动触发扫描 `data/` 目录增量导入。

```bash
curl -X POST http://localhost:8000/documents/ingest
```

### POST /query

一次性 JSON 问答。

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"LandChain 支持哪些文档格式？\"}"
```

### POST /query/stream

SSE 流式问答。

```bash
curl -N -X POST http://localhost:8000/query/stream \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"默认使用什么对话模型？\"}"
```

SSE 事件格式：

- `event: token` — 逐 token 输出
- `event: done` — 完成，含 `sources`
- `event: error` — 错误信息

### POST /chat

多轮对话（带 session memory）。首次不传 `session_id` 会自动生成并在响应中返回。

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"LandChain 支持哪些文档格式？\"}"
```

继续同一会话：

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"your-session-id\", \"message\": \"默认对话模型是什么？\"}"
```

### POST /chat/stream

多轮对话 SSE 流式输出。首个事件 `event: session` 返回 `session_id`。

```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"介绍一下 LandChain\"}"
```

### GET /chat/sessions/{session_id}/history

获取会话历史。

```bash
curl http://localhost:8000/chat/sessions/your-session-id/history
```

### DELETE /chat/sessions/{session_id}

清除会话记忆。

```bash
curl -X DELETE http://localhost:8000/chat/sessions/your-session-id
```

## 闲聊与知识问答分流

日常问候、闲聊、开玩笑等**不需要建知识库**，系统会自动识别并**直连模型**（跳过向量检索）：

- 示例：`你好`、`早上好`、`讲个笑话`、`谢谢`、`在吗`
- 响应里 `mode: "chitchat"`，`sources` 为空，`chunks_used: 0`

业务/资料问题仍走 RAG：

- 示例：`订单 O0001 买了什么酒`、`LandChain 支持哪些文档格式`
- 响应里 `mode: "rag"`，并返回引用来源

可通过 `.env` 关闭直连：`CHITCHAT_DIRECT_ENABLED=false`

## 检索与重排序

检索流程：

1. 向量库召回 `RETRIEVE_K`（默认 12）个候选 chunk
2. Cross-Encoder（默认 `cross-encoder/ms-marco-MiniLM-L-6-v2`）精排
3. 取 `TOP_K`（默认 4）个 chunk 送入 LLM

可通过 `.env` 关闭重排：`RERANK_ENABLED=false`

## CLI 手动导入

```bash
python scripts/ingest_data.py
python scripts/ingest_data.py --force
python scripts/ingest_data.py --dir ./data
```

### PostgreSQL 订单 → RAG

```bash
python scripts/sync_orders_to_rag.py --from 2025-01-01T00:00:00Z --to 2026-06-30T23:59:59Z
python scripts/sync_orders_to_rag.py --from ... --to ... --dry-run
python scripts/sync_orders_to_rag.py --from ... --to ... --generate-only
python scripts/seed_order_test_data.py --count 1000
```

## 配置项（.env）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama 地址（Docker 部署时由 compose 覆盖为 `host.docker.internal`） |
| `OLLAMA_CHAT_MODEL` | `gpt-oss:120b-cloud` | 对话模型（云端推理，需 Ollama 联网） |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | 嵌入模型 |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant 地址（Docker 部署时 compose 覆盖为 `http://qdrant:6333`） |
| `QDRANT_COLLECTION` | `landchain_rag` | Qdrant collection 名称 |
| `QDRANT_API_KEY` | （空） | Qdrant API Key（可选） |
| `POSTGRES_HOST` | `localhost` | PostgreSQL 主机 |
| `POSTGRES_PORT` | `5432` | PostgreSQL 端口 |
| `POSTGRES_USER` | `landchain` | PostgreSQL 用户名 |
| `POSTGRES_PASSWORD` | `landchain` | PostgreSQL 密码 |
| `POSTGRES_DB` | `landchain` | PostgreSQL 数据库名 |
| `POSTGRES_BUSINESS_COLLECTION` | `order` | 业务 JSON 默认集合 |
| `POSTGRES_BUSINESS_ID_FIELD` | `ID` | 业务主键字段 |
| `POSTGRES_BUSINESS_TIME_FIELD` | `created_at` | 时间字段（CLI 区间过滤） |
| `DATA_DIR` | `./data` | 预置文档目录 |
| `CHUNK_SIZE` | `800` | 文本切分大小 |
| `CHUNK_OVERLAP` | `120` | 切分重叠 |
| `TOP_K` | `4` | 重排后送入 LLM 的 chunk 数 |
| `RETRIEVE_K` | `12` | 向量召回候选数 |
| `RERANK_ENABLED` | `true` | 是否启用 Cross-Encoder 重排 |
| `RERANK_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | 重排模型 |
| `SESSION_DB_PATH` | `./storage/sessions.db` | LangGraph 会话持久化 |
| `MAX_UPLOAD_SIZE_MB` | `20` | 上传大小限制 |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | 允许跨域的前端地址（逗号分隔） |

本地离线可用 `qwen3:8b`；中文向量检索更强可换 `qwen3-embedding:0.6b`（需清空向量库后重新导入文档）。

## 前端控制台

仓库内 [`frontend/`](frontend/) 提供 React 聊天控制台，对接现有 RAG API。

### 功能

- 多轮 RAG 聊天（SSE 流式输出、停止生成）
- 引用来源展示与会话持久化
- 文档上传 / `data/` 目录增量导入
- 服务健康与模型信息面板

### 技术栈

React 19 + Vite + TypeScript + Tailwind CSS 4 + React Router

### 启动

需同时运行后端 API 与前端开发服务器：

```powershell
# 终端 1：后端
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 终端 2：前端
cd frontend
npm install
npm run dev
```

浏览器访问：http://localhost:5173

开发环境通过 Vite 代理将 `/api` 转发到 `http://localhost:8000`，无需额外配置 CORS。若前端直连后端地址，请确保 `.env` 中 `CORS_ORIGINS` 包含前端 origin。

### 生产构建

```powershell
cd frontend
npm run build
```

构建产物在 `frontend/dist/`。可通过 Nginx 等静态托管，并设置 `VITE_API_BASE_URL` 指向后端 API 地址。

## 注意事项

- 本服务无鉴权，仅适合本地开发；生产环境请加 API Key 或反向代理
- Ollama 本地推理通常串行，高并发请求会排队
- 上传同名文件会先删除旧 chunk 再写入，避免重复

## 验证清单

1. `GET /health` 显示 `ollama_reachable: true`
2. `data/sample.md` 启动后自动入库，`chunk_count > 0`
3. `POST /query` 返回答案与 `sources`
4. `POST /query/stream` 可看到逐 token SSE
5. `POST /documents/upload` 上传后可立即问答
6. `POST /chat` 多轮对话，`session_id` 可跨请求复用
7. `GET /chat/sessions/{id}/history` 可查看历史
8. Ollama 停服时接口返回 503
9. `python scripts/seed_order_test_data.py` 写入测试订单到 PostgreSQL
10. `python scripts/sync_orders_to_rag.py --from/--to` 生成 `data/orders/` 报告并 ingest
11. `POST /query` 问订单统计 → `sources` 含报告 md 文件路径
12. `--dry-run` 只统计匹配数量，不误写
