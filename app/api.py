"""FastAPI 应用：提供聊天伙伴的 REST 与 SSE 流式接口。"""
from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from .agent import get_agent
from .config import ROOT_DIR, settings
from .memory import get_store
from .models import ChatRequest, ChatResponse
from .personas import PERSONAS

app = FastAPI(title="聊天伙伴", description="基于 LangChain + LangGraph 的聊天伙伴后端", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "chat-friend", "model": settings.llm_model}


@app.get("/api/personas")
async def list_personas() -> list[str]:
    return list(PERSONAS.keys())


@app.get("/api/conversations")
async def list_conversations():
    return get_store().list_conversations()


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    conv = get_store().get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="会话不存在")
    conv["messages"] = get_store().get_history(conversation_id)
    return conv


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    get_store().delete_conversation(conversation_id)
    return {"ok": True}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")
    cid, reply = get_agent().chat(
        message=req.message,
        conversation_id=req.conversation_id,
        persona=req.persona,
    )
    return ChatResponse(conversation_id=cid, message=reply, persona=req.persona)


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest) -> EventSourceResponse:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    async def event_gen() -> AsyncIterator[dict]:
        async for item in get_agent().chat_stream(
            message=req.message,
            conversation_id=req.conversation_id,
            persona=req.persona,
        ):
            # 所有事件的 data 统一带上 type 字段，便于前端解析。
            yield {
                "event": item["type"],
                "data": json.dumps(item, ensure_ascii=False),
            }

    return EventSourceResponse(event_gen())


# 挂载前端静态页面
_static_dir = ROOT_DIR / "web"
if _static_dir.exists():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="web")
