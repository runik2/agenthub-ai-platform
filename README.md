# AgentHub — платформа управления ИИ-агентами

Веб-платформа для работы с ИИ-агентами: конструктор агентов, диалоги с реальной моделью, провайдеры
моделей, учёт токенов и стоимости, аудит действий. Интерфейс на двух языках (RU/EN), тёмная и светлая
темы.

Проект собран в два архитектурных контура:

| Контур | Статус | Компоненты |
|---|---|---|
| `APP_MODE=local` | **работает, проверен** | FastAPI + SQLite (aiosqlite), очередь и планировщик внутри процесса, Ollama на хосте |
| `APP_MODE=docker` | **написан, не проверен** | PostgreSQL + Redis + ARQ worker + отдельный scheduler + nginx |

> Docker-контур никогда не запускался: на машине разработчика не установлены Docker, PostgreSQL и Redis.
> Файлы `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `backend/requirements-docker.txt`
> и адаптер `backend/app/queue/arq.py` написаны по документации, но не проверены ни одной командой.

## Что уже работает

- Первичная настройка администратора, вход по JWT (Argon2id), защищённые маршруты, аудит входов.
- Refresh-сессии, смена и сброс пароля, rate limiting входа, 2FA/TOTP и роли workspace: admin,
  manager, operator, viewer. Приглашения в команду и изоляция ресурсов по workspace.
- CRUD агентов: промпт, приветствие, провайдер, модель, температура, лимит токенов, статус, цвет, теги.
  6 шаблонов агентов, создание из шаблона, дублирование.
- История промптов с авторами, unified diff, rollback и привязка версии промпта к evaluation.
- CRUD провайдеров: Ollama и OpenAI-совместимые, проверка соединения, получение списка моделей,
  цены за 1M токенов, ключи шифруются (Fernet) и никогда не возвращаются в API.
- **Реальный чат с агентом** через Ollama (`llama3.2:3b`) и любой OpenAI-совместимый `base_url`.
  История диалога, системный промпт, запись `llm_usage` (токены, latency, стоимость).
- Дашборд: метрики, график активности, топ агентов, статусы провайдеров за 7/30 дней.
- Workflow-студия: агентные шаги, whitelist-инструменты, условия, параллельные ветки, retries,
  timeout, human approval и тестовый запуск. Конфигурации версионируются и восстанавливаются,
  изменения пишутся в audit log.
- Durable tasks, in-process очередь для local и ARQ/Redis-контур для Docker: статусы, retries,
  сохранённые trace шагов и операторская очередь подтверждений.
- Безопасные интеграции: HTTPS allowlist по домену и пути, запрет секретов в URL, approval для
  опасных действий, HMAC-webhooks, idempotency, retries и журнал вызовов.
- Память агентов и RAG: ручные факты, загрузка TXT/MD/CSV/JSON/PDF/DOCX, импорт веб-страниц,
  чанкинг, embeddings, семантический поиск, источники ответа и версии документов.
- Evaluations: контрольные кейсы, batch-прогоны, pass rate, latency/cost и сравнение моделей.
- Экономика workspace: токены и стоимость по моделям, агентам и workflow, месячные бюджеты,
  warning/exceeded статусы и fallback-провайдер.
- Production-наблюдаемость: readiness DB/queue, Prometheus metrics, JSON-логи с correlation id,
  Grafana dashboard, task traces, integration journal и PostgreSQL backup script.
- Переключатель RU/EN (localStorage, по умолчанию RU), светлая/тёмная тема, адаптив до 390px.
- Command Palette по Ctrl/⌘+K с поиском разделов и keyboard navigation.
- Demo-данные создаются только при явной пометке: у демо-агентов тег `demo`, описание начинается
  с `Demo data ·`, демо-сообщения имеют `metadata.demo = true`.

## Быстрый старт (local, всё проверено)

Нужны: Python 3.12+ (проверено на 3.14), Node 20+ (проверено на 26), Ollama с моделью `llama3.2:3b`.

```bash
# 1. окружение
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt      # Windows
# .venv/bin/pip install -r backend/requirements.txt                      # macOS/Linux

# 2. конфиг (можно не трогать — значения по умолчанию рабочие)
cp backend/.env.example backend/.env

# 3. backend
cd backend
../.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

При первом старте создаётся администратор `admin@agenthub.local` / `admin12345`, база
`backend/data/agenthub.db` и demo-данные. Сменить пароль и секреты — в `backend/.env`.

```bash
# 4. frontend (второй терминал)
cd frontend
npm install
npm run dev          # http://localhost:5173, прокси /api -> 127.0.0.1:8000
```

Проверка API: `http://127.0.0.1:8000/api/docs`.

### Сквозная проверка чата одной командой

```bash
cd backend
../.venv/Scripts/python.exe scripts/smoke_chat.py
```

Скрипт логинится, берёт активного агента, отправляет сообщение в Ollama и печатает usage
(`tokens_in`, `tokens_out`, `latency_ms`, `cost`) и агрегаты аналитики.

## Ollama

```bash
ollama pull llama3.2:3b
ollama serve            # http://127.0.0.1:11434
```

Приложение уже знает про `OLLAMA_BASE_URL=http://127.0.0.1:11434` и создаёт провайдера
`Ollama (local)` с ценой 0. На CPU ответ 3B-модели занимает 10–40 секунд — таймаут клиента
120 секунд, запрос синхронный.

### OpenAI-совместимый провайдер

Добавьте провайдера с типом `OpenAI-совместимый`, `base_url` вида `https://api.openai.com/v1`
(обязательно с `/v1`) и ключом. Ключ шифруется Fernet, в ответах API видны только `has_api_key`
и последние 4 символа. После сохранения нажмите «Проверить соединение» — список моделей подтянется
из `/models`.

## Проверки, которые реально выполнялись

```bash
cd backend
../.venv/Scripts/python.exe -m pytest -q          # полный backend suite
../.venv/Scripts/python.exe -m ruff check app tests
../.venv/Scripts/python.exe -m alembic upgrade head
cd ../frontend && npm run build                    # tsc -b + vite build
```

- `GET /health/live` → 200, `GET /health/ready` проверяет API, DB и очередь и возвращает 503 при деградации.
- Чат через Ollama: ответ получен, `llm_usage` записан (например 87 вход / 37 выход, latency 13.7 s).
- Скриншоты 1280×800 и 390×844 на всех экранах, переключение RU→EN меняет заголовки и меню,
  горизонтального переполнения нет (`document.body.scrollWidth == innerWidth`).

## Архитектура

```
backend/app/
  config.py           # Settings: APP_MODE, DATABASE_URL, секреты
  db/                 # Base, session, ORM-модели пользователей, агентов, workflow, tasks,
                      # knowledge, evaluations, integrations, usage и audit logs
  api/v1/             # auth, agents, providers, conversations, tasks, workflows, tools,
                      # webhooks, knowledge, evaluations, team, analytics, logs, settings, health
  core/               # argon2+JWT, Fernet, единый формат ошибок, пагинация
  services/           # llm (Ollama/openai), chat, pricing, agent_templates, seed, bootstrap
  queue/              # Protocol TaskQueue + InProcessQueue (local) + ArqTaskQueue (docker)
backend/alembic/      # миграции; локальный старт использует create_all
frontend/src/
  i18n/{ru,en}.ts     # весь текст интерфейса; типы гарантируют совпадение ключей
  api/                # fetch-клиент с кодами ошибок, TanStack Query хуки
  components/         # UI-кит, оболочка, command palette и модалки
  pages/              # agents, chat, workflows, tasks, tools, webhooks, knowledge,
                      # memories, evaluations, team, analytics, logs, settings и setup
```

**Двухрежимность.** Слой БД и очередь спрятаны за интерфейсами; режим выбирается `APP_MODE` и
`DATABASE_URL`. `local` — SQLite через `aiosqlite` и `InProcessQueue` в том же процессе, без внешних
сервисов. `docker` — PostgreSQL (`asyncpg`), Redis и ARQ-воркер отдельным контейнером, планировщик
отдельным процессом. Код API от режима не зависит: endpoint не знает, какая очередь под ним.

**i18n.** Ни одной строки в разметке: словари `frontend/src/i18n/ru.ts` и `en.ts`, тип `en` выводится
из `ru`, поэтому пропущенный ключ ломает сборку. Язык в `localStorage`, по умолчанию `ru`.
Ошибки API приходят кодами (`AGENT_NOT_FOUND`, `PROVIDER_TIMEOUT`), текст берётся из словаря
`errors.*` на клиенте.

**Ошибки и безопасность.** Единый формат `{"error": {"code", "message", "details"}}`, коды 400/401/403/
404/409/422/502. Пароли — Argon2id. Секреты провайдеров — Fernet с ключом из `SECRET_ENCRYPTION_KEY`
(или производным от `JWT_SECRET`). Ключи не попадают ни в ответы API, ни в логи; это покрыто тестом.

## Docker-контур (не проверен)

```bash
docker compose up --build      # НЕ ЗАПУСКАЛОСЬ: на машине нет Docker
```

Сервисы: `db` (PostgreSQL 16), `redis`, `api` (миграции + uvicorn), `worker` (ARQ), `scheduler`,
`web` (nginx со сборкой Vite и проксированием `/api`). Переменные: `POSTGRES_PASSWORD`, `JWT_SECRET`,
`OLLAMA_BASE_URL` (для Ollama на хосте — `http://host.docker.internal:11434`).

В этой среде Docker-контур не запускался, поэтому перед production-деплоем нужно выполнить
smoke-проверку образов и внешних сервисов. Воркер обрабатывает durable tasks, а scheduler
создаёт задачи по cron и переотправляет отложенные retries.

### PostgreSQL backup

Скрипт `ops/backup-postgres.sh` создаёт custom-format dump и удаляет архивы старше retention-периода:

```bash
DATABASE_HOST=db DATABASE_USER=agenthub DATABASE_NAME=agenthub \
  PGPASSWORD="$POSTGRES_PASSWORD" BACKUP_DIR=/var/backups/agenthub \
  RETENTION_DAYS=14 ./ops/backup-postgres.sh
```

Архивы нужно хранить на отдельном persistent volume или в объектном хранилище и регулярно
проверять восстановлением через `pg_restore`.

## Production-ограничения

- Docker-контур написан и снабжён healthchecks, но в текущей Windows-среде Docker не установлен,
  поэтому `docker compose up --build` здесь не запускался. Перед деплоем нужно выполнить smoke-тест
  контейнеров, PostgreSQL, Redis, ARQ worker и scheduler в целевой среде.
- Чат пока синхронный: streaming SSE и отмена долгого запроса остаются отдельным следующим улучшением.
- Для production необходимо заменить demo credentials, задать собственные `JWT_SECRET` и
  `SECRET_ENCRYPTION_KEY`, включить HTTPS и вынести backup-архивы на отдельное хранилище.

## Структура репозитория

### Примечание о текущей проверке

Реализованы durable tasks через queue abstraction, retry с `next_run_at`, workflow execution с безопасным
whitelist инструментов, cron scheduler, версионирование и восстановление workflow, operator approval,
audit log, cron scheduler, analytics summary/export и readiness DB/queue. Docker-контур с
Redis/ARQ/PostgreSQL в этой среде не запускался: Docker недоступен; его следует проверить интеграционно.

```
backend/    FastAPI-приложение, тесты, миграции, скрипты
frontend/   React + TypeScript + Vite + Tailwind
docker-compose.yml
```
