# 1C УПП — MCP-сервер документации конфигурации

Поиск по описанию конфигурации 1С УПП: ingestion в Qdrant (два named vectors), MCP-сервер на FastMCP с мультивекторным поиском (RRF).

## Быстрый старт (запуск и подключение по адресу)

1. **Установка** (один раз):
   ```powershell
   cd D:\1C_mcp
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
2. **Qdrant** (должен быть запущен): `docker compose up -d`
3. **Данные** (один раз после появления ZIP):  
   `python -m ingest "D:\1C_mcp\ОписаниеКонфигурации.zip"`
4. **Запуск сервера** (одна команда из корня проекта):
   - **PowerShell** (из `D:\1C_mcp`): `.\run_server.ps1`
   - **CMD** или двойной щелчок: `run_server.bat` (или `.\run_server.bat`)
   - Из любой папки: полный путь к скрипту, например `& "D:\1C_mcp\run_server.ps1"` в PowerShell или `D:\1C_mcp\run_server.bat` в CMD.
5. **Подключение в Cursor**: в проекте уже есть конфиг **.cursor/mcp.json** — сервер «1c-upp-docs» подхватится при открытии папки. Либо вручную: Settings → MCP → добавьте сервер типа `streamableHttp` с URL `http://127.0.0.1:8000/mcp`. После смены конфига перезапустите Cursor.

Настройки (Qdrant URL, порт, путь) задаются в файле **.env** в корне проекта.

**Порт 8000 занят?** (ошибка 10048) — завершите старый процесс или смените порт в `.env` (`MCP_PORT=8001`). Узнать, кто занял порт, и завершить:
```powershell
netstat -ano | findstr :8000
taskkill /PID <номер_из_колонки_PID> /F
```

## Требования

- Python 3.10+
- Docker (для Qdrant) или внешний Qdrant

## Установка

```powershell
cd D:\1C_mcp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Запуск Qdrant

```powershell
docker compose up -d
```

Проверка: <http://localhost:6333/dashboard>.

**Если образ не скачивается** (ошибка про `127.0.0.1:10801` или registry): Docker использует прокси, который не запущен. Отключите прокси в Docker Desktop (Settings → Resources → Proxies) или уберите переменные `HTTP_PROXY`/`HTTPS_PROXY`, затем перезапустите Docker и снова выполните `docker compose up -d`.

## Деплой в Docker и Dokploy (доступ к MCP из любого места)

Стек можно запустить целиком в Docker: поднимаются **Qdrant** и **MCP-сервер**. После деплоя на сервер (в т.ч. через Dokploy) к MCP можно подключаться по URL из Cursor или другого клиента с любого компьютера.

### Локально (Docker Compose)

Из корня проекта:

```powershell
docker compose up -d
```

- **Qdrant**: http://localhost:6333  
- **MCP**: http://localhost:8000/mcp  

Подключение в Cursor: URL `http://localhost:8000/mcp` (тип `streamableHttp`).

Данные в Qdrant на сервере: положите `ОписаниеКонфигурации.zip` в volume `ingest_data` и перезапустите MCP (см. раздел «Деплой в Dokploy»). Локально: `python -m ingest "путь/к/zip"` при поднятом Qdrant.

### Деплой в Dokploy

1. **Репозиторий / файлы**  
   Залейте проект в Git или загрузите в Dokploy так, чтобы в корне были `Dockerfile`, `docker-compose.yml`, `requirements.txt`, `config.py`, `embedding.py`, `qdrant_ops.py`, `mcp_server.py`.

2. **Создание приложения**  
   В Dokploy: **Docker Compose** → создать приложение → указать репозиторий или загрузку файлов, корень — каталог с `docker-compose.yml`.

3. **Доступ к MCP по домену (Traefik)**  
   В `docker-compose.yml` в сервисе `mcp` раскомментируйте блок с метками Traefik и сетью (в конце файла):

   - Замените `mcp.your-domain.com` на ваш домен (например, `mcp.example.com`).
   - Раскомментируйте `networks:` и `dokploy-network` (external).
   - У сервиса `mcp` раскомментируйте `networks: default, dokploy-network`.

   Либо задайте домен через UI Dokploy: в приложении → **Domains** → добавьте домен для сервиса MCP (порт контейнера 8000, путь `/mcp` остаётся в URL).

4. **Переменные окружения**  
   В Dokploy в настройках приложения можно задать (при необходимости): `COLLECTION_NAME`, `EMBED_MODEL`. `QDRANT_URL` в compose уже указан как `http://qdrant:6333`.

5. **Сборка и запуск**  
   Запустите деплой. После старта MCP будет доступен по адресу вида:

   - По домену: `https://mcp.your-domain.com/mcp`  
   - Либо по IP и порту, если порт 8000 проброшен на хост: `http://<IP-сервера>:8000/mcp`

6. **Ingestion на сервере (без ПК разработчика)**  
   ZIP не в Git — один раз кладёте на сервер в volume `ingest_data` (путь в контейнере: `/data/ОписаниеКонфигурации.zip`).

   **Шаг 1.** Скопировать ZIP в volume (SSH на сервер, из каталога проекта Dokploy):
   ```bash
   docker cp ОписаниеКонфигурации.zip $(docker compose ps -q mcp):/data/
   ```
   Либо смонтировать файл в Dokploy → Volumes, если UI позволяет.

   **Шаг 2.** Перезапустить MCP — при старте entrypoint сам загрузит данные, если коллекции ещё нет:
   ```bash
   docker compose restart mcp
   ```
   В логах MCP: `Коллекция пустая, запуск ingestion...` (10–30 мин).

   **Повторная загрузка вручную:**
   ```bash
   docker compose --profile ingest run --rm ingest
   ```

   Переменная `INGEST_ZIP_PATH` (по умолчанию `/data/ОписаниеКонфигурации.zip`) — путь к ZIP внутри контейнера MCP.

7. **Подключение в Cursor из любого места**  
   Settings → MCP → добавьте сервер типа **streamableHttp** с URL:

   - `https://mcp.your-domain.com/mcp` (если настроен домен и HTTPS),  
   - или `http://<IP-сервера>:8000/mcp` (если доступ по IP и порту).

   После сохранения перезапустите Cursor.

### Кратко

| Где запущено | MCP URL для подключения |
|--------------|--------------------------|
| Локально (docker compose) | `http://localhost:8000/mcp` |
| Сервер по IP, порт 8000 открыт | `http://<IP>:8000/mcp` |
| Dokploy + домен (Traefik) | `https://mcp.your-domain.com/mcp` |

## Конфигурация (.env)

Файл **.env** в корне проекта задаёт все параметры. Пример уже создан; при необходимости отредактируйте:

| Переменная       | Описание                          | По умолчанию в .env |
|------------------|-----------------------------------|----------------------|
| `QDRANT_URL`     | URL Qdrant                        | `http://localhost:6333` |
| `COLLECTION_NAME`| Имя коллекции                     | `1c_upp_docs` |
| `EMBED_MODEL`    | Модель sentence-transformers     | `paraphrase-multilingual-MiniLM-L12-v2` |
| `MCP_TRANSPORT`  | Транспорт: `http` (подключение по URL) или `stdio` | `http` |
| `MCP_HOST`       | Хост для HTTP (для доступа с других ПК задайте `0.0.0.0`) | `127.0.0.1` |
| `MCP_PORT`       | Порт для HTTP                    | `8000` |
| `MCP_PATH`       | Путь для HTTP                    | `/mcp` |

## Ingestion

Подготовьте ZIP с описанием конфигурации:

- В корне ZIP: файл **objects.csv** (разделитель `;`, кодировка UTF-8).
- Колонки CSV: **Имя объекта**, **Тип объекта**, **Синоним**, **Файл** (путь к MD относительно корня архива).
- В архиве — markdown-файлы по путям из колонки «Файл».

Запуск загрузки (из папки проекта; .env подхватится автоматически):

```powershell
python -m ingest "D:\1C_mcp\ОписаниеКонфигурации.zip"
```

Обработка граничных случаев:

- **BOM в CSV**: чтение в `utf-8-sig`, заголовки нормализуются.
- **Кириллица**: везде UTF-8; модель `paraphrase-multilingual-MiniLM-L12-v2` поддерживает русский.
- **Отсутствующий MD-файл**: запись не пропускается, в payload поле `doc` будет пустым, в лог пишется предупреждение.
- **Неверная/несуществующая коллекция**: при поиске и при `get_1c_object_doc` возвращается явная ошибка «Коллекция не найдена. Сначала выполните ingestion.»

## MCP-сервер

По умолчанию в **.env** задан режим **HTTP**: запускаете сервер и подключаетесь по адресу в поисковой строке клиента.

- **Запуск**: одна команда из корня проекта — `.\run_server.ps1` (PowerShell) или `.\run_server.bat` (CMD / двойной щелчок). Либо `python mcp_server.py` при уже активированном venv.
- **Адрес для подключения**: `http://localhost:8000/mcp` (с другого ПК — `http://<IP>:8000/mcp`)

Для режима **stdio** (клиент сам запускает процесс) в .env поставьте `MCP_TRANSPORT=stdio` и настройте клиент на команду `python mcp_server.py`.

### Инструменты (tools)

1. **search_1c_docs**  
   `search_1c_docs(query, object_type=None, limit=10, use_multivector=True)`  
   Поиск по документации. При `use_multivector=True` используется RRF по векторам `object_name` и `friendly_name`.

2. **get_1c_object_doc**  
   `get_1c_object_doc(object_name)`  
   Получить по имени объекта payload: `object_name`, `object_type`, `synonym`, `file_name`, `doc`.

3. **health_check**  
   Проверка доступности и наличия коллекции (удобно использовать вместо отдельного HTTP `/health`).

## Структура проекта

```
D:\1C_mcp\
  .env             # настройки (создан по умолчанию, можно править)
  config.py        # загрузка .env и конфиг
  embedding.py     # sentence-transformers
  qdrant_ops.py    # коллекция, named vectors, поиск (single + RRF)
  ingest.py        # pipeline: ZIP → CSV → MD → Qdrant
  mcp_server.py    # FastMCP: search_1c_docs, get_1c_object_doc, health_check
  run_server.bat   # запуск MCP-сервера (CMD / двойной клик)
  run_server.ps1   # запуск одной командой из корня: .\run_server.ps1
  requirements.txt
  docker-compose.yml
  Dockerfile
  .dockerignore
  README.md
```

## Health endpoint

Отдельный HTTP endpoint `/health` не поднимается. Для проверки состояния используйте tool **health_check** или доступность MCP (например, `fastmcp list` по URL сервера). При необходимости можно добавить отдельное приложение (FastAPI/Starlette) с маршрутом `GET /health`.
