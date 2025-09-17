# 数学建模 RAG 智能问答系统

## 🎯 项目简介

基于 LangChain + Django + React 构建的数学建模领域专业问答系统，提供智能文档检索和专业问答能力。

### ✨ 核心特性

- **🧠 智能问答**: 基于 RAG 技术的数学建模专业问答
- **📚 文档管理**: 支持 PDF、Word、TXT 文档上传和索引
- **🔍 混合检索**: 向量检索 + BM25 + 智能重排序
- **💬 流式输出**: 实时流式回答展示
- **👥 用户管理**: 完整的用户认证和权限系统
- **🎨 现代UI**: 响应式设计，优雅的用户体验

### 🏗️ 技术架构

**后端**:
- Django 5.2 + Django REST Framework
- LangChain + FAISS 向量存储
- OpenRouter API (DeepSeek 模型)
- 本地 Ollama 嵌入模型

**前端**:
- React 18 + Ant Design 5
- Vite 构建工具
- 现代化响应式设计

**核心能力**:
- 增强的检索策略（查询扩展、去重过滤）
- 异步流式处理
- 智能文档分块和索引

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 16+
- Ollama (本地嵌入模型)

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd LANGCHAIN-RAG
```

2. **安装 Python 依赖**
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

3. **安装前端依赖**
```bash
cd frontend
npm install
```

4. **配置环境变量**
```bash
cp configs/settings.example.env .env
# 编辑 .env 文件，填入必要的配置
```

5. **安装 Ollama 模型**
```bash
ollama pull nomic-embed-text:v1.5
```

6. **初始化数据库**
```bash
cd backend
python manage.py migrate
```

### 运行应用

1. **启动后端**
```bash
cd backend
python -m uvicorn rag_backend.asgi:application --reload --host 0.0.0.0 --port 9000
```

2. **启动前端**
```bash
cd frontend
npm run dev
```

3. **访问应用**
- 前端界面: http://localhost:5173
- 后端 API: http://localhost:9000

## 📖 使用指南

### 文档上传

管理员登录后可以上传文档：
- 支持格式：PDF、Word (.docx)、TXT
- 自动文档解析和向量索引
- 增量更新支持

### 智能问答

1. 在问答界面输入数学建模相关问题
2. 系统自动检索相关文档片段
3. 基于检索结果生成专业回答
4. 查看参考资料和相关度评分

### 用户管理

- 用户注册和登录
- 管理员权限管理
- 用户状态控制（冻结/解冻）

## 🔧 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `OPENROUTER_API_KEY` | OpenRouter API 密钥 | - |
| `DOCS_ROOT` | 文档存储目录 | `./docs` |
| `VECTOR_STORE_PATH` | 向量索引路径 | `vector_store/index.faiss` |
| `EMBED_MODEL` | 嵌入模型名称 | `nomic-embed-text:v1.5` |
| `CHUNK_SIZE` | 文档分块大小 | `1200` |
| `CHUNK_OVERLAP` | 分块重叠大小 | `120` |

### API 配置

前端 API 代理配置 (vite.config.js):
```javascript
proxy: {
  '/api': {
    target: 'http://127.0.0.1:9000',
    changeOrigin: true
  }
}
```

## 🛠️ 开发说明

### 项目结构

```
LANGCHAIN-RAG/
├── backend/              # Django 后端
│   ├── rag_api/         # API 应用
│   └── rag_backend/     # 项目配置
├── frontend/            # React 前端
│   └── src/
├── src/                 # RAG 核心逻辑
│   ├── rag/            # 检索和嵌入
│   ├── ingestion/      # 文档处理
│   └── config.py       # 配置管理
├── scripts/            # 工具脚本
└── tests/              # 测试文件
```

### 核心优化

1. **检索增强**:
   - 查询预处理和扩展
   - 智能去重过滤
   - 自适应检索策略

2. **UI 优化**:
   - 简化界面设计
   - 流式输出支持
   - 响应式布局

3. **架构精简**:
   - 统一后端架构（移除 FastAPI 冗余）
   - 清理不必要文件
   - 优化配置管理

### API 接口

#### 核心接口

- `POST /api/ask` - 问答接口
- `POST /api/ask/stream` - 流式问答
- `POST /api/upload` - 文档上传
- `POST /api/ingest` - 文档索引
- `GET /api/health` - 健康检查

#### 用户管理

- `POST /api/register` - 用户注册
- `POST /api/login` - 用户登录
- `GET /api/admin/users` - 用户列表（管理员）

## 🔍 问题排查

### 常见问题

1. **Ollama 连接失败**
   - 确保 Ollama 服务运行: `ollama serve`
   - 检查模型是否安装: `ollama list`

2. **文档上传失败**
   - 检查文件格式和大小限制
   - 确认用户具有管理员权限

3. **向量检索无结果**
   - 运行 `/api/ingest` 重建索引
   - 检查文档目录配置

## 📝 更新日志

### v2.0 (优化版本)

**🎯 架构优化**:
- 统一后端架构，移除 FastAPI 冗余
- 精简项目结构，清理不必要文件
- 优化配置管理和环境变量

**🚀 功能增强**:
- 增强的检索策略和查询扩展
- 流式输出支持和实时响应
- 改进的文档分块和索引策略

**💻 UI 重构**:
- 全新的响应式界面设计
- 简化用户交互流程
- 优化移动端适配

**🧹 代码清理**:
- 移除冗余组件和过时文件
- 统一代码风格和规范
- 完善错误处理机制

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request 来改进项目：

1. Fork 项目
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- [LangChain](https://github.com/langchain-ai/langchain) - RAG 框架
- [Django](https://www.djangoproject.com/) - Web 框架
- [React](https://reactjs.org/) - 前端框架
- [Ant Design](https://ant.design/) - UI 组件库
- [FAISS](https://github.com/facebookresearch/faiss) - 向量检索