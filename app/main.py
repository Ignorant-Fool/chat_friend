"""应用入口：``python -m app.main`` 或 ``uvicorn app.main:app``。"""
from __future__ import annotations

import logging
import os

import uvicorn

from .api import app
from .config import settings


def _configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> None:
    _configure_logging()
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    print(f"聊天伙伴已启动：http://{host}:{port}")
    print(f"模型：{settings.llm_model}  端点：{settings.llm_base_url}")
    uvicorn.run(app, host=host, port=port, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()
