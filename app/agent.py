"""LangGraph 聊天伙伴 Agent。

用 StateGraph 构建一个带记忆、带人设的多节点对话流程：

    entry → load_history → respond ──→ (是否流式) → stream / astream
                        ↑      │
                        └──────┘（保存消息后结束）

节点说明：
- load_history：从 SQLite 读取该会话最近的历史，注入 state。
- respond：调用 ChatOpenAI 生成回复。
- save_and_finish：把用户消息与助手回复写回 SQLite，并自动生成会话标题。

通过 ``build_agent()`` 得到编译好的图，可复用 ``.stream()`` / ``.invoke()``。
"""
from __future__ import annotations

import logging
from typing import Annotated, AsyncIterator, Optional, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from .config import settings
from .memory import MemoryStore, get_store
from .personas import get_system_prompt

logger = logging.getLogger(__name__)


class ChatState(TypedDict, total=False):
    """Graph 节点之间传递的状态。"""

    conversation_id: str
    persona: str
    user_message: str
    # 由 add_messages 归并的消息列表（历史 + 新消息）
    messages: Annotated[list[BaseMessage], add_messages]
    response: str


def _build_llm(streaming: bool = False) -> ChatOpenAI:
    """构建 ChatOpenAI（指向 DeepSeek 兼容端点）。

    兼容 langchain-openai 0.x 与 1.x 的字段命名差异：
    旧版用 ``api_key`` / ``base_url`` / ``model``，
    1.x 改用 ``openai_api_key`` / ``openai_api_base`` / ``model_name``。
    """
    try:
        fields = ChatOpenAI.model_fields
    except AttributeError:
        fields = None

    if fields is not None:
        kwargs = dict(
            openai_api_key=settings.llm_api_key,
            openai_api_base=settings.llm_base_url,
            model_name=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            streaming=streaming,
        )
    else:
        kwargs = dict(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            streaming=streaming,
        )
    return ChatOpenAI(**kwargs)


class ChatBuddyAgent:
    def __init__(self, store: Optional[MemoryStore] = None) -> None:
        self.store = store or get_store()
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(ChatState)

        builder.add_node("load_history", self._load_history)
        builder.add_node("respond", self._respond)

        builder.set_entry_point("load_history")
        builder.add_edge("load_history", "respond")
        builder.add_edge("respond", END)

        return builder.compile()

    # ---------------- 节点 ----------------
    def _load_history(self, state: ChatState) -> ChatState:
        """读取历史并组装 messages（system + 历史）。

        当前用户消息已由调用方把 HumanMessage 放入 state["messages"]，
        此处只补充 system 与历史，交给 add_messages 归并。
        """
        history = (
            self.store.get_history(state["conversation_id"])
            if state.get("conversation_id")
            else []
        )
        messages: list[BaseMessage] = [
            SystemMessage(content=get_system_prompt(state["persona"]))
        ]
        for item in history:
            if item["role"] == "user":
                messages.append(HumanMessage(content=item["content"]))
            elif item["role"] == "assistant":
                messages.append(AIMessage(content=item["content"]))
        return {"messages": messages}

    def _respond(self, state: ChatState) -> ChatState:
        """调用 LLM 生成回复。"""
        llm = _build_llm(streaming=False)
        result = llm.invoke(state["messages"])
        return {"response": result.content, **state}

    # ---------------- 对外接口 ----------------
    def _ensure_conversation(self, conversation_id: Optional[str], persona: str) -> str:
        """确保会话存在；为空则新建。"""
        if conversation_id and self.store.get_conversation(conversation_id):
            return conversation_id
        return self.store.create_conversation(persona=persona)

    def _maybe_title(self, conversation_id: str, user_message: str) -> None:
        """会话标题为空时，用首条用户消息生成简短标题。"""
        conv = self.store.get_conversation(conversation_id)
        if conv and conv["title"] in ("新对话", ""):
            title = user_message.strip().replace("\n", " ")[:20] or "新对话"
            self.store.update_conversation_title(conversation_id, title)

    async def chat_stream(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        persona: str = "buddy",
    ) -> AsyncIterator[dict]:
        """流式聊天，逐块产出响应。

        产出格式：
        - {"type": "start", "conversation_id": str}
        - {"type": "token", "content": str}
        - {"type": "end", "content": str（完整回复）}
        """
        cid = self._ensure_conversation(conversation_id, persona)
        self._maybe_title(cid, message)
        self.store.add_message(cid, "user", message)

        history = self.store.get_history(cid)
        messages: list[BaseMessage] = [
            SystemMessage(content=get_system_prompt(persona))
        ]
        for item in history:
            if item["role"] == "user":
                messages.append(HumanMessage(content=item["content"]))
            elif item["role"] == "assistant":
                messages.append(AIMessage(content=item["content"]))

        llm = _build_llm(streaming=True)
        full = ""
        yield {"type": "start", "conversation_id": cid}
        try:
            async for chunk in llm.astream(messages):
                piece = chunk.content if isinstance(chunk.content, str) else ""
                if piece:
                    full += piece
                    yield {"type": "token", "content": piece}
            # DeepSeek 某些情况下可能通过额外字段输出，这里兜底
            if not full:
                result = llm.invoke(messages)
                full = result.content if isinstance(result.content, str) else str(result.content)
                yield {"type": "token", "content": full}
        except Exception as exc:  # noqa: BLE001
            logger.exception("流式生成失败：%s", exc)
            yield {"type": "error", "content": f"生成回复失败：{exc}"}
            return
        finally:
            if full:
                self.store.add_message(cid, "assistant", full)
            yield {"type": "end", "content": full}

    def chat(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        persona: str = "buddy",
    ) -> tuple[str, str]:
        """非流式聊天，返回 (conversation_id, 回复内容)。"""
        cid = self._ensure_conversation(conversation_id, persona)
        self._maybe_title(cid, message)
        self.store.add_message(cid, "user", message)

        result = self.graph.invoke(
            {
                "conversation_id": cid,
                "persona": persona,
                "user_message": message,
                "messages": [HumanMessage(content=message)],
            }
        )
        response = result.get("response", "")
        self.store.add_message(cid, "assistant", response)
        return cid, response


# 进程级单例
_agent: Optional[ChatBuddyAgent] = None


def get_agent() -> ChatBuddyAgent:
    global _agent
    if _agent is None:
        _agent = ChatBuddyAgent()
    return _agent
