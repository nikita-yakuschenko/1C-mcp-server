# MCP-сервер 1C UPP Docs: HTTP на порту 8000, подключается к Qdrant по сети
FROM python:3.11-slim

WORKDIR /app

# Системные зависимости для sentence-transformers (опционально, для части моделей)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Сначала ставим PyTorch только под CPU — иначе pip тянет nvidia-* и сборка долгая/падает без GPU
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py embedding.py qdrant_ops.py ingest.py mcp_server.py entrypoint.sh ./
RUN chmod +x entrypoint.sh
COPY data/ОписаниеКонфигурации.zip /data/ОписаниеКонфигурации.zip

# Порт HTTP MCP (uvicorn)
EXPOSE 8000

# Переменные задаются через docker-compose; по умолчанию — HTTP на 0.0.0.0
ENV MCP_TRANSPORT=http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000 \
    MCP_PATH=/mcp

ENTRYPOINT ["./entrypoint.sh"]
