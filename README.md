# 数学建模 RAG 系统 (LangChain + OpenRouter + 本地Ollama)

## 目标
针对 `2025国赛创新型算法+源代码汇总！` 目录内的 .docx / .pdf 文档，建立高保真解析、增量更新、结构化检索与数学建模问答生成能力。（PDF 当前仅提取纯文字，忽略图片 / 公式版式）

## 组件概览
- 解析：python-docx + OMML -> LaTeX（公式保真）
- 嵌入：本地 Ollama 模型 `nomic-embed-text:v1.5`
- LLM：OpenRouter `deepseek/deepseek-chat-v3.1:free`
- 索引：FAISS （后续可替换向量数据库）
- 检索：向量检索 + （预留）BM25 + 可选重排序
- 服务：FastAPI `/ingest`, `/ask`, `/health`

## 快速开始

### 安装
```
python -m venv .venv
./.venv/Scripts/Activate.ps1
pip install -r requirements.txt
copy configs\settings.example.env .env
# 编辑 .env 填入 OPENROUTER_API_KEY
ollama pull nomic-embed-text:v1.5
```

### Windows 平台特别说明（PowerShell）
在 Windows 上运行本项目时，FAISS 和本地 Ollama 可能需要额外准备。下面是常见问题与推荐的安装步骤：

- 推荐先启用虚拟环境（PowerShell 举例）：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

- FAISS（向量索引）
	- Windows 对官方 faiss 包支持有限。推荐使用 conda（推荐）或查找适配的 wheel：
		- Conda（推荐）：
			```powershell
			# 如果使用 Anaconda/Miniconda
			conda create -n rag python=3.10 -y
			conda activate rag
			conda install -c conda-forge faiss-cpu -y
			pip install -r requirements.txt
			```
		- Pip：如果你不使用 conda，可尝试查找 community wheel（针对 Windows 的 faiss 轮子），或者在 Windows 下使用 faiss 的替代（例如 use sqlite + annoy/hnswlib）作为备选。
	- 备注：如果遇到 faiss 安装问题，另外的稳妥做法是使用 WSL2（Ubuntu 子系统）来运行服务并把数据目录挂载到 Windows 文件系统。

- Ollama（本地嵌入模型）
	- 先在机器上安装 Ollama：参考 https://ollama.com 安装说明（Windows 支持的版本/安装方式可能随时间变化）。安装完成后确保 Ollama 守护进程在本机运行（通常为 localhost:11434）。
	- 拉取嵌入模型并测试：
		```powershell
		# 拉取模型（示例）
		ollama pull nomic-embed-text:v1.5

		# 测试嵌入（调用 ollama CLI）
		ollama run nomic-embed-text:v1.5 --text "测试文本"
		```
	- 如果 Ollama 在 Windows 上不可用或不想使用本地服务，可改用远端 embedding（如 OpenAI/other providers）或在本地运行 Ollama 的 Linux 容器/WSL2。

- 运行/调试常用命令（PowerShell）
	```powershell
	# 激活虚拟环境
	.\.venv\Scripts\Activate.ps1

	# 增量摄取（示例）
	python -m src.cli ingest

	# 全量重建索引（会清空旧索引）
	python -m src.cli ingest --rebuild

	# 启动 API 服务（开发）
	python -m src.api.server

	# 运行 tests（仅项目 tests 目录）
	D:\langchain-RAG\.venv\Scripts\python.exe -m pytest -q tests
	```

- pre-commit（在虚拟环境中运行）
	- 如果 `pre-commit` 无法直接从 PowerShell 调用，建议使用虚拟环境的 python -m 形式：
		```powershell
		.\.venv\Scripts\Activate.ps1
		python -m pip install --upgrade pre-commit
		python -m pre_commit install
		python -m pre_commit run --all-files
		```

以上说明覆盖了大多数 Windows 常见问题与可行替代方案；如果你使用 WSL2/远端主机，建议在 Linux 环境中安装 FAISS 与 Ollama 以减少兼容性问题。

### 摄取文档 (.docx + .pdf)
```
python -m src.cli ingest               # 增量更新
python -m src.cli ingest --rebuild     # 删除旧索引后全量重建
```

## 准备检索文档目录

默认项目会使用仓库根的 `docs/` 目录作为待解析文档（DOCS_ROOT）。请把要用于检索的原始文件放在该目录下，支持的文件类型包括：`.docx`, `.pdf`, `.txt`。

建议：
- 每次批量导入前先确认文件大小，不要将大于 50 MB 的文件直接放入 `docs/`（大文件会显著增加索引和上传压力）。
- 对于扫描版 PDF，建议先做 OCR，然后再放入 `docs/`。
- 如果你需要自定义路径或在生产环境使用不同目录，请在 `.env` 设置 `DOCS_ROOT=/path/to/your/docs` 或在 `src/config.py` 中更改 `DOCS_ROOT`。

示例：
```powershell
# 将文档放到默认 docs 目录
mkdir docs
Copy-Item -Path "C:\some\folder\*.docx" -Destination docs\ -Recurse

# 或者在 .env 中指定自定义路径
Set-Content -Path .env -Value "DOCS_ROOT=./my_documents" -Encoding UTF8
```

注意：`docs/` 目录应包含原始文档文件，任何由摄取生成的中间文件（向量索引、meta.jsonl、exports 等）不应放入此目录，以避免误提交。


### 单轮问答
```
python -m src.cli ask -q "请比较AHP与熵权法的权重获取差异" --show-context
```

### 交互式 REPL
```
python -m src.cli repl --show-context
```

### 终端图形界面 (TUI)
安装依赖（若未安装 rich / textual）：
```
pip install rich textual
```
启动：
```
python -m src.cli tui
```
功能：F5 增量摄取 / F6 重建索引 / 输入问题回车检索并回答；右侧可查看回答与日志增量。

### 批量问题
```
python -m src.cli ask -f questions.txt --json > answers.json
```

### 启动 API 服务
```
python -m src.api.server
```

### 摄取日志说明
执行 `python -m src.cli ingest` 现在会额外输出统计：
- [INGEST][STAT] 段落: total= 总段落数 / docx= 来自 docx / pdf= 来自 pdf / math= 含解析到的 LaTeX 片段 / placeholder= 含 `/*math*/` 占位
- [INGEST][STAT] 表格: total= 表格元素数
- [INGEST][STAT] 解析错误: total= 错误元素数（并列出前 3 个错误来源）
- [INGEST][STAT] 公式解析覆盖率≈X% = (段落总数 - placeholder 段落) / 段落总数

用于快速评估：
- 解析是否成功遍历全部文件
- 公式（OMML）转换的覆盖程度
- PDF 文本段落占比（判断是否需要更强 PDF 解析）

## 健壮性增强 (解析 & 摄取)
新增特性：
- 解析版本 `PARSER_VERSION` 写入元素 (file_hash, file_mtime, parser_version)
- PDF 体积限制: 超过 `MAX_PDF_MB` (默认25MB) 标记 error 跳过
- PDF 低文本比检测: 文本字节/文件字节 < `LOW_PDF_TEXT_RATIO` (默认0.02) 判定疑似扫描版，标记 `pdf_low_text_ratio`
- 覆盖率报警: 公式解析覆盖率 <70% 输出 [INGEST][WARN]
- CLI ingest 输出解析版本及统计

环境变量：
| 名称 | 默认 | 说明 |
|------|------|------|
| MAX_PDF_MB | 25 | PDF 超过此大小(MB)不解析 |
| LOW_PDF_TEXT_RATIO | 0.02 | PDF 文本字节/总字节 比例阈值 |

后续可基于 (file_hash, parser_version) 实现增量重解析 / 过期检测 / 已删除文件向量清理。

## API 使用说明

### 基础信息
- Base URL（本地默认）：`http://127.0.0.1:8000`
- OpenAPI 文档（交互调试）：启动后访问 `http://127.0.0.1:8000/docs`
- 返回格式：JSON
- 编码：UTF-8

### 端点一览
| 方法 | 路径 | 说明 | 请求体 | 主要返回字段 |
|------|------|------|--------|--------------|
| GET  | /health | 健康检查 | 无 | status |
| POST | /ingest | 重新扫描根目录，增量嵌入新增块 | 无 | raw_items, chunks, added |
| POST | /ask | 检索 + LLM 生成回答 | JSON(AskRequest) | answer, contexts[] |

### /health
请求：
```
GET /health
```
响应示例：
```json
{"status":"ok"}
```

### /ingest
说明：
- 会遍历配置的 `DOCS_ROOT` 目录 (.env 可修改)
- 对新增（按内容 hash 去重）的分块执行嵌入，写入向量索引
- 已存在块不会重复嵌入

请求：
```
POST /ingest
Content-Type: application/json
```
无请求体。

响应字段：
- raw_items: 原始解析元素数（段落/表格/错误等）
- chunks: 切分后候选块总数
- added: 本次真正新写入向量数（跳过重复 & 嵌入失败的）

示例（PowerShell）：
```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/ingest -Method POST
```

### /ask
请求体 AskRequest：
```json
{
	"question": "AHP 与 熵权法的区别?",
	"top_k": 6,
	"bm25_weight": 0.35
}
```
字段说明：
- question (必填)：用户问题
- top_k (可选, 默认6)：返回前K个混合检索片段参与回答
- bm25_weight (可选, 默认0.35)：BM25 权重 w，组合分数=(1-w)*向量 + w*BM25

响应示例：
```json
{
	"answer": "...模型生成的结构化回答...",
	"contexts": [
		{"score": 0.8123, "source": "2025国赛.../案例 1：...docx", "hash": "abcd1234..."},
		{"score": 0.7901, "source": "2025国赛.../案例 2：...docx", "hash": "ef56..."}
	]
}
```

PowerShell 调用示例：
```powershell
$body = @{ question = "AHP 与 熵权法 差异"; top_k = 6; bm25_weight = 0.35 } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/ask -Method POST -ContentType 'application/json' -Body $body
```

curl 示例：
```bash
curl -X POST http://127.0.0.1:8000/ask \
	-H "Content-Type: application/json" \
	-d '{"question":"AHP 与 熵权法 差异","top_k":6,"bm25_weight":0.35}'
```

### 环境变量影响
| 变量 | 用途 | 示例 |
|------|------|------|
| OPENROUTER_API_KEY | OpenRouter 访问密钥 | sk-xxxx | 
| DOCS_ROOT | 文档根目录 | 2025国赛创新型算法+源代码汇总！ |
| VECTOR_STORE_PATH | 向量索引文件路径 | vector_store/index.faiss |
| METADATA_STORE_PATH | 元数据 JSONL | vector_store/meta.jsonl |
| EMBED_MODEL | Ollama 嵌入模型名 | nomic-embed-text:v1.5 |
| CHUNK_SIZE | 分块目标长度 | 1200 |
| CHUNK_OVERLAP | 分块重叠字符数 | 120 |

修改 `.env` 后需要重新运行服务 & 重新 ingest 以生效（向量路径、分块参数等）。

### 返回 contexts 说明
- score：混合排序后的综合得分（经归一化近似余弦 + BM25 权重融合）
- source：原始文件路径（可用于定位来源）
- hash：该 chunk 的唯一哈希（用于去重/缓存）

### 常见错误与排查
| 场景 | 现象 | 处理 |
|------|------|------|
| 未先 ingest 就 ask | contexts 为空或相关性差 | 先调用 /ingest 或 CLI ingest |
| OPENROUTER_API_KEY 缺失 | 500 或 LLM 请求失败 | 在 .env 写入并重启 |
| 嵌入 502/超时 | added 数偏小 | 重试 /ingest，检查本地 Ollama 负载 |
| PDF 乱码 | 非 UTF-8 或扫描版 | 需 OCR / 重新获取文本版 |

### 典型集成流程伪代码
```python
import requests

requests.post('http://127.0.0.1:8000/ingest')  # 可按需定期调用
payload = {"question":"如何选择熵权法或AHP?","top_k":6,"bm25_weight":0.35}
r = requests.post('http://127.0.0.1:8000/ask', json=payload, timeout=60)
data = r.json()
print(data['answer'])
for ctx in data['contexts']:
		print(ctx['score'], ctx['source'])
```

### 扩展建议
- 增加 /metrics 暴露 Prometheus 监控
- 增加 /rebuild 清空并重建索引（当前可手动删文件）
- 增加 /ask 流式响应（使用 Server-Sent Events 或 WebSocket）
- 增加 answer 缓存（question+top_k+bm25_weight 哈希）


## 检索策略
默认使用 向量检索 + BM25 混合：组合分数 = (1-w)*向量 + w*BM25，参数 `--bm25-weight` 可调 (0 ~ 1)。

## 公式解析
当前实现基础 OMML -> LaTeX 支持：
- 分数 (m:f -> \frac{a}{b})
- 上标 / 下标 / 上下标 (m:sSup / m:sSub / m:sSubSup)
- 根号 (m:rad, 含可选次数 \sqrt[n]{ })
- 简单求和 / 积分 / 连乘 (m:nary 中的 ∑ / ∫ / ∏ 识别并封装表达式)

仍未覆盖的结构（矩阵、对齐、多层嵌套复杂版式）会回退到纯文本或占位 `/*math*/`。遇到无法解析的部分将占位 `/*math*/`，后续可扩展完整节点映射。

PDF 内公式若为图片或复杂排版暂不解析，仅抽取连续文本块（按空行分段）。

## 失败重试
LLM 请求采用指数退避重试 (最多3次)。

## 后续可选增强
- 更完整 OMML -> LaTeX 映射
- 表格结构化回答
- Reranker (Cross-Encoder) 引入
- 多轮对话上下文记忆策略
- Docker 化与监控 (Prometheus)

## 稳健扩展建议（Roadmap 要点）
1. 检索质量
	- 增加交叉编码重排序 (bge-reranker / Cohere rerank)
	- 召回分数归一策略统一（向量 + BM25 分布对齐）
2. 解析增强
	- PDF 表格解析 (pdfplumber)
	- OMML 全量节点到 LaTeX（根号/上下标/积分/矩阵）
3. Fallback 策略
	- 嵌入失败自动切换本地 sentence-transformers 备份模型
	- LLM 超时降级为更小模型 / 直接片段拼接应答
4. 运行与可观测
	- /metrics 暴露 Prometheus 指标
	- 失败 chunk hash 持久化与再尝试队列
	- Answer 缓存 (question+参数 指纹)
5. 数据治理
	- 文件级增量：记录每文件 mtime+hash，删除已消失文件对应向量
	- 块级压缩：长尾低访问块归档/重建
6. 安全 & 访问控制
	- API Key / Token 鉴权
	- 请求频率限制 (fastapi-limiter)

---

## 前端（RAG 智能检索系统 Web UI）

### 技术栈
- React 18 + Ant Design 5
- Vite 构建
- react-markdown、react-router-dom

### 安装与启动
```
cd frontend
npm install
npm run dev
```
默认端口 5173，已自动代理 /api 到后端服务。

### 主要功能
- 首页：文档上传（支持 PDF、Word、TXT）、智能问答（多模型切换、Markdown 渲染、流式输出）
- 文档检索页：已上传文档列表、检索输入、结果高亮展示
- 设置弹窗（预留）：API Key、模型参数、主题切换

### 页面导航
- 顶部导航栏可切换首页、文档检索、设置
- 支持响应式布局，移动端适配

### 前后端协作
- 前端通过 HTTP 请求与后端 API 交互，接口完全兼容
- 前后端目录分离，互不影响


