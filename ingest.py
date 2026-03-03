# Ingestion: распаковка ZIP, чтение objects.csv и MD, эмбеддинги, загрузка в Qdrant
import csv
import logging
import zipfile
from pathlib import Path
from typing import List, Tuple

import config
from qdrant_ops import VECTOR_FRIENDLY_NAME, VECTOR_OBJECT_NAME, ensure_collection, upsert_batch

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Ожидаемые колонки в objects.csv (после нормализации BOM/пробелов)
COL_OBJECT = "Имя объекта"
COL_TYPE = "Тип объекта"
COL_SYNONYM = "Синоним"
COL_FILE = "Файл"

# Размер батча для upsert
BATCH_SIZE = 32


def _normalize_header(name: str) -> str:
    return (name or "").strip().replace("\ufeff", "")


def read_objects_csv(csv_path: Path) -> List[dict]:
    """Читает objects.csv (sep=';'), обрабатывает BOM и кириллицу."""
    rows = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        raw_fieldnames = list(reader.fieldnames or [])
        fieldnames = [_normalize_header(h) for h in raw_fieldnames]
        for row in reader:
            # DictReader по умолчанию использует исходные имена; нормализуем ключи
            normalized = {}
            for i, key in enumerate(raw_fieldnames):
                new_key = fieldnames[i] if i < len(fieldnames) else _normalize_header(key)
                normalized[new_key] = (row.get(key) or "").strip()
            rows.append(normalized)
    return rows


def read_md(base_path: Path, file_rel: str) -> str:
    """Читает содержимое MD-файла. Если файла нет — возвращает пустую строку и логирует."""
    if not (file_rel or file_rel.strip()):
        return ""
    path = base_path / file_rel.strip().lstrip("/\\")
    if not path.is_file():
        logger.warning("Файл не найден: %s (ожидался относительно %s)", path, base_path)
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.warning("Ошибка чтения файла %s: %s", path, e)
        return ""


def run_ingestion(zip_path: str) -> Tuple[int, int]:
    """
    Распаковывает ZIP, читает objects.csv и MD по колонке Файл,
    генерирует эмбеддинги, заливает в Qdrant.
    Возвращает (успешно загружено, пропущено/ошибки).
    """
    zip_path = Path(zip_path)
    if not zip_path.is_file():
        raise FileNotFoundError(f"ZIP не найден: {zip_path}")

    work_dir = zip_path.parent / (zip_path.stem + "_ingest")
    work_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(work_dir)

    csv_candidate = work_dir / "objects.csv"
    if not csv_candidate.is_file():
        raise FileNotFoundError(
            f"В архиве нет objects.csv. Проверьте корень ZIP: {list(work_dir.iterdir())}"
        )

    rows = read_objects_csv(csv_candidate)
    if not rows:
        logger.warning("objects.csv пустой или без данных")
        return 0, 0

    # Проверяем наличие колонки Файл
    if COL_FILE not in rows[0]:
        raise ValueError(
            f"В CSV ожидается колонка '{COL_FILE}'. Найдены: {list(rows[0].keys())}"
        )

    ensure_collection()
    loaded = 0
    skipped = 0

    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]
        ids = []
        payloads = []
        object_name_texts = []
        friendly_name_texts = []

        for r in batch:
            object_name = (r.get(COL_OBJECT) or "").strip()
            object_type = (r.get(COL_TYPE) or "").strip()
            synonym = (r.get(COL_SYNONYM) or "").strip()
            file_name = (r.get(COL_FILE) or "").strip()
            if not object_name:
                skipped += 1
                continue
            doc = read_md(work_dir, file_name)
            # Тексты для двух векторов: по имени объекта и по синониму+документ
            object_name_texts.append(object_name)
            friendly_name_texts.append(synonym if synonym else object_name)
            ids.append(object_name)
            payloads.append({
                "object_name": object_name,
                "object_type": object_type,
                "synonym": synonym,
                "file_name": file_name,
                "doc": doc,
            })
            loaded += 1

        if ids:
            upsert_batch(ids, payloads, object_name_texts, friendly_name_texts)
            logger.info("Загружено записей: %d (батч до %d)", loaded, start + len(batch))

    return loaded, skipped


def main() -> None:
    import sys
    if len(sys.argv) < 2:
        print("Использование: python -m ingest <путь к ОписаниеКонфигурации.zip>")
        sys.exit(1)
    zip_path = sys.argv[1]
    try:
        loaded, skipped = run_ingestion(zip_path)
        print(f"Готово. Загружено: {loaded}, пропущено: {skipped}")
    except Exception as e:
        logger.exception("%s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
