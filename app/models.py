"""数据模型定义（Pydantic）。"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    """一条聊天消息。"""

    role: Literal["user", "assistant", "system"] = "user"
    content: str = ""


class Conversation(BaseModel):
    """一次会话。"""

    id: Optional[str] = None
    title: str = "新对话"
    persona: str = "buddy"  # 伙伴人设名
    created_at: str = ""
    updated_at: str = ""


class ChatRequest(BaseModel):
    """聊天请求体。"""

    message: str = Field(..., description="用户输入的消息")
    conversation_id: Optional[str] = Field(None, description="会话 ID；为空则新建会话")
    persona: str = Field("buddy", description="伙伴人设")
    stream: bool = Field(False, description="是否流式返回")


class ChatResponse(BaseModel):
    """聊天响应体（非流式）。"""

    conversation_id: str
    message: str
    persona: str
