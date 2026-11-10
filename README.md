# 聊天伙伴 (Chat Friend)

一个基于 **LangChain + LangGraph** 框架的「聊天伙伴」项目，后端使用 Python + FastAPI，前端提供简洁的网页聊天界面。支持多角色「人设」、会话历史持久化（SQLite）、以及流式（SSE）回复。

## 功能特性

- 🤖 **LangGraph 多节点 Agent**：`load_history → respond` 状态图，带记忆的对话流程
- 🧠 **SQLite 持久化记忆**：会话、消息历史、长期记忆本地存储，重启不丢失
- 🎭 **多角色人设**：温暖伙伴 / 元气鼓励 / 理性学者，可自由扩展
- ⚡ **流式输出**：基于 SSE 的逐 token 实时回复
- 🖥️ **开箱即用前端**：简洁聊天页面 + 会话管理 + 人设切换
- 🔌 **OpenAI 兼容协议**：默认接入 DeepSeek API，可换任意兼容端点

## 项目结构

```
chat_friend/
├── app/
│   ├── __init__.py
│   ├── config.py        # 配置（模型、密钥、存储路径）
│   ├── models.py        # Pydantic 数据模型
│   ├── personas.py      # 人设（system prompt）定义
│   ├── memory.py        # SQLite 记忆存储层
│   ├── agent.py         # LangGraph Agent（核心）
│   ├── api.py           # FastAPI 路由 + SSE
│   └── main.py          # 启动入口
├── web/
│   └── index.html       # 前端聊天页面
├── requirements.txt
├── .env.example         # 环境变量示例
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，填入你的 API Key：

```bash
cp .env.example .env
```

默认已使用 DeepSeek 兼容端点，可通过以下变量切换模型：

| 变量 | 说明 | 默认值 |
|---|---|---|
| `DEEPSEEK_API_KEY` | API 密钥 | — |
| `DEEPSEEK_BASE_URL` | OpenAI 兼容端点 | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | 模型名 | `deepseek-chat` |
| `DB_PATH` | SQLite 文件路径 | `data/chat_friend.db` |

### 3. 启动服务

```bash
# 方式一：直接运行
python -m app.main

# 方式二：uvicorn
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开浏览器访问 **http://127.0.0.1:8000** 即可开始聊天。

## API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 健康检查 |
| GET | `/api/personas` | 列出所有人设 |
| GET | `/api/conversations` | 列出所有会话 |
| GET | `/api/conversations/{id}` | 获取会话 + 消息历史 |
| DELETE | `/api/conversations/{id}` | 删除会话 |
| POST | `/api/chat` | 非流式聊天，返回完整回复 |
| POST | `/api/chat/stream` | 流式聊天（SSE） |

### 请求示例

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "你好，今天有点累", "persona": "buddy"}'
```

响应：

```json
{ "conversation_id": "abc123...", "message": "……", "persona": "buddy" }
```

## 扩展自定义人设

在 `app/personas.py` 的 `PERSONAS` 字典中添加新条目即可，例如：

```python
"poet": "你是一个富有诗意的伙伴，用优美的语言回应……"
```

## 技术栈

- LangChain / LangGraph —— Agent 编排与记忆
- langchain-openai —— 兼容 OpenAI 协议的模型客户端
- FastAPI + uvicorn —— Web 服务
- sse-starlette —— 流式输出
- SQLite —— 本地持久化
