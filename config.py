# Конфигурация из переменных окружения и .env
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Загружаем .env из папки проекта (рядом с config.py)
load_dotenv(Path(__file__).resolve().parent / ".env")


def _str(value: Optional[str], default: str) -> str:
    return (value or "").strip() or default


def _int(value: Optional[str], default: int) -> int:
    try:
        return int((value or "").strip()) if (value or "").strip() else default
    except ValueError:
        return default


# Qdrant
QDRANT_URL: str = _str(os.environ.get("QDRANT_URL"), "http://localhost:6333")
COLLECTION_NAME: str = _str(os.environ.get("COLLECTION_NAME"), "1c_upp_docs")

# Модель эмбеддингов (sentence-transformers)
EMBED_MODEL: str = _str(
    os.environ.get("EMBED_MODEL"), "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

# MCP server
MCP_TRANSPORT: str = _str(os.environ.get("MCP_TRANSPORT"), "stdio")
MCP_HOST: str = _str(os.environ.get("MCP_HOST"), "127.0.0.1")  # только localhost; для доступа с других ПК задайте 0.0.0.0
MCP_PORT: int = _int(os.environ.get("MCP_PORT"), "8000")
MCP_PATH: str = _str(os.environ.get("MCP_PATH"), "/mcp")
