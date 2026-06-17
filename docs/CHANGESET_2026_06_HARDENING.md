# LandChain 改造清单（2026-06）

本清单汇总本轮连续改造，便于评审、验收与后续发布。

## 1) 安全基线

- Agent 强制 API Key 开关：`AGENT_REQUIRE_API_KEY=true`
- Agent Shell 默认关闭：`AGENT_SHELL_ENABLED=false`
- Shell 执行器收敛为 `shell=False`，并拦截危险连接符
- 公共接口可选 API Key 保护：
  - `PUBLIC_API_KEY`
  - `PUBLIC_API_KEY_HEADER`
  - 覆盖 `/query` `/chat` `/documents`

## 2) 错误处理统一

- 新增全局异常处理：
  - `HTTPException`
  - `RequestValidationError`
  - `Exception` 兜底
- 统一错误返回结构：
  - `success=false`
  - `error.code`
  - `error.message`
  - `error.details`（可选）

## 3) 稳定性与并发

- 将同步重操作移出事件循环（线程池桥接）：
  - `query/chat/documents` 同步调用统一走 `run_sync`
  - SSE 同步迭代器通过 `iter_sync_in_thread` 进行异步桥接

## 4) 审计字段标准化

- 审计日志新增字段（向后兼容）：
  - `actor`
  - `source`
  - `duration_ms`
  - `result_summary`
  - `resolved_by`
- 覆盖 Agent 工具调用与 shell 审批决策链路

## 5) 可观测性

- 引入请求级追踪字段：
  - `X-Request-Id`（透传/自动生成）
  - 响应头回传 `X-Request-Id`
- 关键性能日志统一字段：
  - `request_id`
  - `session_id`（chat 场景）
  - `mode/chunks/tokens/retrieval_ms/llm_ms/total_ms`
- 新增性能聚合脚本：
  - `scripts/perf_log_summary.py`
  - 支持 `--since` 与 `--event-prefix`

## 6) 回归验证

- 单测从初始基线扩展到 20+，覆盖：
  - 安全策略
  - 错误处理
  - 审计字段
  - ingest/retrieval/health 关键路径
  - 线程桥接
  - 观测聚合脚本
- 新增回归入口脚本：
  - `python scripts/regression_check.py`
  - 可选 `--log-file` 执行性能日志解析校验
