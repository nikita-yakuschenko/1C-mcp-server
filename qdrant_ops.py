# Работа с Qdrant: коллекция с named vectors, поиск (в т.ч. RRF)
import uuid
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient, models as qmodels

import config
from embedding import encode, get_embedding_dimension

# Имена векторов в коллекции
VECTOR_OBJECT_NAME = "object_name"
VECTOR_FRIENDLY_NAME = "friendly_name"


class QdrantCollectionError(Exception):
    """Коллекция не существует или недоступна."""
    pass


class QdrantConnectionError(Exception):
    """Ошибка подключения к Qdrant."""
    pass


def _client() -> QdrantClient:
    return QdrantClient(url=config.QDRANT_URL)


def _object_name_to_point_id(object_name: str) -> uuid.UUID:
    """Детерминированный UUID от имени объекта (Qdrant принимает только integer или UUID)."""
    return uuid.uuid5(uuid.NAMESPACE_OID, object_name)


def ensure_collection() -> None:
    """Создаёт коллекцию с двумя named vectors, если её ещё нет."""
    client = _client()
    if client.collection_exists(config.COLLECTION_NAME):
        return
    dim = get_embedding_dimension(config.EMBED_MODEL)
    client.create_collection(
        collection_name=config.COLLECTION_NAME,
        vectors_config={
            VECTOR_OBJECT_NAME: qmodels.VectorParams(
                size=dim,
                distance=qmodels.Distance.COSINE,
            ),
            VECTOR_FRIENDLY_NAME: qmodels.VectorParams(
                size=dim,
                distance=qmodels.Distance.COSINE,
            ),
        },
    )


def collection_exists() -> bool:
    """Проверяет существование коллекции."""
    try:
        return _client().collection_exists(config.COLLECTION_NAME)
    except Exception:
        return False


def upsert_batch(
    ids: List[str],
    payloads: List[Dict[str, Any]],
    object_name_texts: List[str],
    friendly_name_texts: List[str],
) -> None:
    """Заливает батч точек с двумя векторами и payload. ids — имена объектов (в Qdrant сохраняются как UUID)."""
    if not ids:
        return
    obj_vectors = encode(object_name_texts, config.EMBED_MODEL)
    friendly_vectors = encode(friendly_name_texts, config.EMBED_MODEL)
    points = []
    for pid, payload, ov, fv in zip(
        ids, payloads, obj_vectors, friendly_vectors
    ):
        points.append(
            qmodels.PointStruct(
                id=_object_name_to_point_id(pid),
                vector={
                    VECTOR_OBJECT_NAME: ov,
                    VECTOR_FRIENDLY_NAME: fv,
                },
                payload=payload,
            )
        )
    _client().upsert(
        collection_name=config.COLLECTION_NAME,
        points=points,
    )


def search_single(
    query: str,
    vector_name: str,
    object_type: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Поиск по одному вектору с опциональным фильтром по object_type."""
    try:
        client = _client()
        if not client.collection_exists(config.COLLECTION_NAME):
            raise QdrantCollectionError(
                f"Коллекция '{config.COLLECTION_NAME}' не найдена. Сначала выполните ingestion."
            )
    except Exception as e:
        raise QdrantConnectionError(f"Ошибка подключения к Qdrant: {e}") from e

    qvec = encode([query], config.EMBED_MODEL)[0]
    filter_cond = None
    if object_type and object_type.strip():
        filter_cond = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="object_type",
                    match=qmodels.MatchValue(value=object_type.strip()),
                )
            ]
        )
    result = client.search(
        collection_name=config.COLLECTION_NAME,
        query_vector=(vector_name, qvec),
        query_filter=filter_cond,
        limit=limit,
        with_payload=True,
    )
    return [
        {
            "id": str(hit.id),
            "score": hit.score,
            "payload": hit.payload or {},
        }
        for hit in result
    ]


def search_multivector_rrf(
    query: str,
    object_type: Optional[str] = None,
    limit: int = 10,
    prefetch_limit: int = 20,
) -> List[Dict[str, Any]]:
    """Мультивекторный поиск через Prefetch + RRF (Fusion)."""
    try:
        client = _client()
        if not client.collection_exists(config.COLLECTION_NAME):
            raise QdrantCollectionError(
                f"Коллекция '{config.COLLECTION_NAME}' не найдена. Сначала выполните ingestion."
            )
    except Exception as e:
        raise QdrantConnectionError(f"Ошибка подключения к Qdrant: {e}") from e

    qvec = encode([query], config.EMBED_MODEL)[0]
    filter_cond = None
    if object_type and object_type.strip():
        filter_cond = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="object_type",
                    match=qmodels.MatchValue(value=object_type.strip()),
                )
            ]
        )
    prefetches = [
        qmodels.Prefetch(
            query=qvec,
            using=VECTOR_OBJECT_NAME,
            limit=prefetch_limit,
        ),
        qmodels.Prefetch(
            query=qvec,
            using=VECTOR_FRIENDLY_NAME,
            limit=prefetch_limit,
        ),
    ]
    result = client.query_points(
        collection_name=config.COLLECTION_NAME,
        prefetch=prefetches,
        query=qmodels.FusionQuery(fusion=qmodels.Fusion.RRF),
        limit=limit,
        query_filter=filter_cond,
        with_payload=True,
    )
    points = result.points or []
    return [
        {
            "id": str(p.id),
            "score": getattr(p, "score", None),
            "payload": p.payload or {},
        }
        for p in points
    ]


def get_point_by_id(object_name: str) -> Optional[Dict[str, Any]]:
    """Получить точку по имени объекта (object_name)."""
    try:
        client = _client()
        if not client.collection_exists(config.COLLECTION_NAME):
            raise QdrantCollectionError(
                f"Коллекция '{config.COLLECTION_NAME}' не найдена."
            )
        point_id = _object_name_to_point_id(object_name)
        result = client.retrieve(
            collection_name=config.COLLECTION_NAME,
            ids=[point_id],
            with_payload=True,
        )
        if not result:
            return None
        p = result[0]
        return {"id": str(p.id), "payload": p.payload or {}}
    except Exception as e:
        raise QdrantConnectionError(f"Ошибка подключения к Qdrant: {e}") from e
