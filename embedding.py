# Эмбеддинги через sentence-transformers (поддержка кириллицы)
from typing import List

from sentence_transformers import SentenceTransformer


_model: SentenceTransformer | None = None


def get_model(model_name: str) -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(model_name)
    return _model


def get_embedding_dimension(model_name: str) -> int:
    model = get_model(model_name)
    return model.get_sentence_embedding_dimension()


def encode(texts: List[str], model_name: str) -> List[List[float]]:
    if not texts:
        return []
    model = get_model(model_name)
    # normalize: пустые строки заменяем на пробел, чтобы не ломать encode
    normalized = [t if t and t.strip() else " " for t in texts]
    embeddings = model.encode(normalized, convert_to_numpy=True)
    return embeddings.tolist()
