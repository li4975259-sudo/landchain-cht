# LandChain 示例知识库

LandChain 是一个基于 LangChain、FastAPI 和本地 Ollama 的 RAG（检索增强生成）服务。

## 功能

- 支持 PDF、TXT、Markdown 文档导入
- 使用 Ollama 本地模型进行 embedding 和问答
- 提供 HTTP API：健康检查、文档上传、知识库问答（含 SSE 流式）

## 默认模型

- 对话模型：gpt-oss:120b-cloud
- 嵌入模型：nomic-embed-text

## 启动方式

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 测试问题

你可以问：「LandChain 支持哪些文档格式？」或「默认使用什么对话模型？」
