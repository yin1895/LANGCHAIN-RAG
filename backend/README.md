# Django 后端（最小可用骨架）

- 目的：提升吞吐与可维护性，在不重写 RAG 核心逻辑的前提下，复用 `src` 目录代码。
- 入口：`manage.py`（Django） + `rag_backend/asgi.py`（ASGI）。
- App：`rag_api` 提供 `/api/health`、`/api/ask` 两个端点；`ask` 为异步视图，带并发信号量限制。

启动（WSL / Linux 环境）

```bash
# 激活你的虚拟环境后
pip install -r requirements.txt
# 迁移（使用内置 sqlite）
python backend/manage.py migrate
# 开发启动（ASGI）
python -m uvicorn rag_backend.asgi:application --app-dir backend --reload --host 0.0.0.0 --port 9000
```

生产部署（示例）

```bash
# 多 worker，限制并发，缩短 keep-alive
D:\langchain-RAG\.venv\Scripts\python.exe -m uvicorn rag_backend.asgi:application --app-dir backend --host 0.0.0.0 --port 9000 --workers 4 --limit-concurrency 256 --timeout-keep-alive 5
```

登录失败排查（Windows/前后端直连 JSON）
- 确保两端使用同一密钥与数据库路径：
	- `AUTH_SECRET_KEY` 与 `AUTH_DB_PATH` 两个环境变量同时提供给 FastAPI 与 Django（如仅用 Django 可只设置 Django 进程环境）。
- 前端/客户端为 JSON POST 时，Django 端点已设置 `csrf_exempt`，避免 CSRF 拦截；生产环境建议改为 Token/Session 并开启 CSRF。
- 调用示例（PowerShell）：
	```powershell
	$env:AUTH_SECRET_KEY = "your-secret-key"
	$body = @{ username='test'; password='pass' } | ConvertTo-Json
	Invoke-RestMethod -Uri http://127.0.0.1:9000/api/login -Method Post -ContentType 'application/json' -Body $body
	```

性能要点
- 复用 `src` 的全局单例（embedding/store/llm），避免重复初始化。
- `ask` 使用 `asyncio.Semaphore` 控制同时进行的 LLM 调用数量，避免过载。
- 后续建议：将 `/ingest` 与重建索引迁移为 Celery 任务，完成后原子替换向量库。

前端对接
- Vite 前端可将 API 基础路径改为 `http://localhost:9000/api`。

```text
注意：当前仅实现了 /ask 和 /health；/ingest 可按需要迁移。
```
