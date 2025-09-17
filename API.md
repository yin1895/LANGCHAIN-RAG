# API 文档

## 基础信息

- 基础 URL: `http://localhost:9000/api`
- 认证方式: Bearer Token (JWT)
- 数据格式: JSON
- 后端框架: Django + Django REST Framework

## 核心接口

### 问答接口

#### POST /ask
普通问答接口

**请求参数:**
```json
{
  "question": "如何选择合适的优化算法？",
  "top_k": 6,
  "bm25_weight": 0.35,
  "include_content": true
}
```

**响应:**
```json
{
  "answer": "根据问题类型选择优化算法...",
  "contexts": [
    {
      "source": "optimization_guide.pdf",
      "content": "优化算法选择依据...",
      "score": 0.95,
      "hash": "abc123"
    }
  ]
}
```

#### POST /ask/stream
流式问答接口

**请求参数:** 同 `/ask`

**响应:** Server-Sent Events (SSE)
```
data: {"type": "contexts", "data": [...]}
data: {"type": "chunk", "data": "回答片段"}
data: {"type": "end"}
```

### 文档管理

#### POST /upload
文档上传接口（需要管理员权限）

**请求:** multipart/form-data
- `file`: 文档文件 (PDF/Word/TXT)

**响应:**
```json
{
  "success": true,
  "filename": "document.pdf"
}
```

#### POST /ingest
文档索引接口

**响应:**
```json
{
  "raw_items": 150,
  "chunks": 300,
  "added": 50
}
```

### 用户管理

#### POST /register
用户注册

**请求:**
```json
{
  "username": "user123",
  "password": "password123"
}
```

#### POST /login
用户登录

**请求:**
```json
{
  "username": "user123",
  "password": "password123"
}
```

**响应:**
```json
{
  "token": "eyJ0eXAi...",
  "is_admin": false
}
```

### 系统接口

#### GET /health
健康检查

**响应:**
```json
{
  "status": "ok",
  "embedding": "available",
  "vector_store": "loaded"
}
```

## 错误处理

### 错误格式
```json
{
  "error": "error_code",
  "detail": "详细错误信息"
}
```

### 常见错误码

- `400` - 请求参数错误
- `401` - 未认证
- `403` - 权限不足
- `404` - 资源不存在
- `500` - 服务器内部错误
- `502` - LLM 服务错误

## 使用示例

### JavaScript
```javascript
// 问答请求
const response = await fetch('/api/ask', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({
    question: '什么是线性规划？',
    top_k: 6
  })
});

const data = await response.json();
console.log(data.answer);
```

### Python
```python
import requests

# 登录获取 token
login_resp = requests.post('http://localhost:9000/api/login', json={
    'username': 'admin',
    'password': 'password'
})
token = login_resp.json()['token']

# 发起问答
response = requests.post('http://localhost:9000/api/ask', 
    headers={'Authorization': f'Bearer {token}'},
    json={'question': '如何建立数学模型？'}
)

print(response.json()['answer'])
```

## 流式接口使用

### JavaScript (SSE)
```javascript
const eventSource = new EventSource('/api/ask/stream?' + new URLSearchParams({
  question: '什么是优化算法？'
}));

eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);
  if (data.type === 'chunk') {
    console.log(data.data); // 输出回答片段
  } else if (data.type === 'end') {
    eventSource.close();
  }
};
```