#!/bin/sh
set -e

wait_for_qdrant() {
  python - <<'PY'
import os, time, sys
import httpx

url = os.environ.get("QDRANT_URL", "http://qdrant:6333").rstrip("/")
for _ in range(60):
    try:
        r = httpx.get(f"{url}/collections", timeout=3.0)
        if r.status_code < 500:
            sys.exit(0)
    except Exception:
        pass
    time.sleep(2)
print("Qdrant недоступен", file=sys.stderr)
sys.exit(1)
PY
}

maybe_ingest() {
  python - <<'PY'
import os
import subprocess
import sys

zip_path = os.environ.get("INGEST_ZIP_PATH", "").strip()
if not zip_path:
    sys.exit(0)
if not os.path.isfile(zip_path):
    print(f"INGEST_ZIP_PATH={zip_path} — файл не найден, ingestion пропущен", file=sys.stderr)
    sys.exit(0)

from qdrant_ops import collection_has_data
import time

done_marker = os.environ.get("INGEST_DONE_PATH", "/data/.ingest_done")
if os.path.isfile(done_marker):
    print("Ingestion уже выполнялся (.ingest_done), пропуск")
    sys.exit(0)

for attempt in range(5):
    if collection_has_data():
        print("Коллекция уже заполнена, ingestion не нужен")
        sys.exit(0)
    if attempt < 4:
        time.sleep(2)

print(f"Коллекция пустая, ingestion в фоне: {zip_path}", flush=True)
subprocess.Popen(
    [sys.executable, "-m", "ingest", zip_path],
    stdout=None,
    stderr=None,
)
PY
}

wait_for_qdrant
maybe_ingest
exec python mcp_server.py
