# MCP-сервер FastMCP: поиск по документации 1С и получение объекта
from typing import Any, Optional

from fastmcp import FastMCP

import config


class AcceptSSEMiddleware:
    """Подставляет Accept для MCP; для GET /mcp из браузера возвращает страницу-заглушку (обход 406)."""
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        # lifespan должен дойти до Starlette/FastMCP (иначе MCP-сессии не инициализируются → 404)
        if scope.get("type") == "lifespan":
            await self.app(scope, receive, send)
            return
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path = (scope.get("path") or "").strip()
        method = (scope.get("method") or "GET").upper()
        headers_list = list(scope.get("headers") or [])
        accept_raw = next((v for k, v in headers_list if k.lower() == b"accept"), b"")
        has_sse = b"text/event-stream" in (accept_raw or b"").lower()
        # GET /mcp из браузера (без Accept: text/event-stream) — отдаём страницу, чтобы «открылось»
        if path == "/mcp" and method == "GET" and not has_sse:
            body = (
                "<html><head><meta charset='utf-8'><title>1C UPP MCP</title></head><body>"
                "<h1>MCP-сервер 1C UPP Docs</h1><p>Эндпоинт работает. Подключайтесь по адресу "
                "<code>http://localhost:8000/mcp</code> из Cursor или другого MCP-клиента.</p></body></html>"
            ).encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"text/html; charset=utf-8"], [b"content-length", str(len(body)).encode()]],
            })
            await send({"type": "http.response.body", "body": body})
            return
        # Подставляем Accept для MCP (Traefik/прокси могут съесть исходный заголовок)
        new_headers = [(k, v) for k, v in headers_list if k.lower() != b"accept"]
        if method == "POST":
            accept_value = b"application/json"
        else:
            accept_value = b"application/json, text/event-stream"
        new_headers.append((b"Accept", accept_value))
        new_scope = {**scope, "headers": new_headers}
        await self.app(new_scope, receive, send)


def _patch_streamable_http_accept() -> None:
    """Отключаем жёсткую проверку Accept (ломается за Traefik и Cursor)."""
    from mcp.server.streamable_http import StreamableHTTPServerTransport

    def _check_accept_headers(_self: Any, _request: Any) -> tuple[bool, bool]:
        return True, True

    async def _validate_accept_header(_self: Any, _request: Any, _scope: Any, _send: Any) -> bool:
        return True

    StreamableHTTPServerTransport._check_accept_headers = _check_accept_headers
    StreamableHTTPServerTransport._validate_accept_header = _validate_accept_header


from qdrant_ops import (
    QdrantCollectionError,
    QdrantConnectionError,
    VECTOR_FRIENDLY_NAME,
    VECTOR_OBJECT_NAME,
    get_point_by_id,
    search_multivector_rrf,
    search_single,
)

mcp = FastMCP("1C UPP Docs")


def _safe_search(
    query: str,
    object_type: Optional[str] = None,
    limit: int = 10,
    use_multivector: bool = True,
) -> dict:
    """Обёртка поиска с единым форматом ошибок."""
    try:
        if use_multivector:
            hits = search_multivector_rrf(
                query=query,
                object_type=object_type,
                limit=limit,
            )
        else:
            # Поиск только по полю object_name (имя объекта)
            hits = search_single(
                query=query,
                vector_name=VECTOR_OBJECT_NAME,
                object_type=object_type,
                limit=limit,
            )
        return {"success": True, "hits": hits, "count": len(hits)}
    except QdrantCollectionError as e:
        return {"success": False, "error": str(e), "hits": [], "count": 0}
    except QdrantConnectionError as e:
        return {"success": False, "error": str(e), "hits": [], "count": 0}


@mcp.tool
def search_1c_docs(
    query: str,
    object_type: Optional[str] = None,
    limit: int = 10,
    use_multivector: bool = True,
) -> dict:
    """
    Поиск по документации конфигурации 1С УПП.
    query: поисковый запрос (естественный язык, поддерживается кириллица).
    object_type: опциональный фильтр по типу объекта (например, Справочник, Документ).
    limit: максимальное число результатов (по умолчанию 10).
    use_multivector: если True — поиск по двум векторам (имя объекта и синоним/описание) с RRF; если False — только по имени объекта.
    """
    if not (query or str(query).strip()):
        return {"success": False, "error": "Параметр query не может быть пустым.", "hits": [], "count": 0}
    limit = max(1, min(100, int(limit) if isinstance(limit, int) else 10))
    return _safe_search(
        query=str(query).strip(),
        object_type=str(object_type).strip() if object_type else None,
        limit=limit,
        use_multivector=bool(use_multivector),
    )


@mcp.tool
def get_1c_object_doc(object_name: str) -> dict:
    """
    Получить полное описание объекта конфигурации 1С по его имени.
    object_name: имя объекта (как в метаданных, например код справочника или документа).
    Возвращает payload точки: object_name, object_type, synonym, file_name, doc (текст из MD).
    """
    if not (object_name or str(object_name).strip()):
        return {"success": False, "error": "Параметр object_name не может быть пустым.", "payload": None}
    name = str(object_name).strip()
    try:
        point = get_point_by_id(name)
        if point is None:
            return {"success": False, "error": f"Объект с именем '{name}' не найден в коллекции.", "payload": None}
        return {"success": True, "payload": point.get("payload")}
    except QdrantCollectionError as e:
        return {"success": False, "error": str(e), "payload": None}
    except QdrantConnectionError as e:
        return {"success": False, "error": str(e), "payload": None}


@mcp.tool
def health_check() -> dict:
    """
    Проверка доступности сервиса и Qdrant.
    Возвращает status и доступность коллекции.
    """
    try:
        from qdrant_ops import collection_has_data
        qdrant_ok = collection_has_data()
        return {
            "status": "ok",
            "qdrant_reachable": True,
            "collection_exists": qdrant_ok,
            "collection_name": config.COLLECTION_NAME,
        }
    except Exception as e:
        return {
            "status": "degraded",
            "qdrant_reachable": False,
            "collection_exists": False,
            "error": str(e),
        }


def _run() -> None:
    transport = (config.MCP_TRANSPORT or "stdio").strip().lower()
    if transport == "http":
        import uvicorn
        from starlette.middleware import Middleware

        _patch_streamable_http_accept()
        app = mcp.http_app(
            path=config.MCP_PATH,
            json_response=True,
            middleware=[Middleware(AcceptSSEMiddleware)],
        )
        uvicorn.run(
            app,
            host=config.MCP_HOST,
            port=config.MCP_PORT,
            log_level="info",
            lifespan="on",
        )
    else:
        mcp.run()


if __name__ == "__main__":
    _run()
