# Architecture

A modular monolith: one FastAPI service, a Celery worker and scheduler, PostgreSQL for durable state, Redis for cache, sessions, rate limiting and the task queue. Every AI call goes through one gateway; every product is a thin configuration over a shared agent.

## System context

```
 Browser SPA / API clients / Telegram / WhatsApp
          |  JWT  or  X-API-Key
          v
 +------------------------------ FastAPI (main.py) ------------------------------+
 | CORS | per-API-key rate limit | global error handler                          |
 | /auth  /billing  /monitoring  /content  /telegram  /business  /products       |
 +-----+------------------+---------------------------+---------------------------+
       |                  |                           |
       v                  v                           v
  core/auth          bots/* + agents/*          core/api/billing.py (Razorpay, PayPal)
  JWT, API keys,     (domain logic)
  Google OAuth,            |
  plan checks              v
       |            core/gateway/ai_router.py   <-- single LLM entry point
       |             model per task, cache, fallback, cost
       |                   |            |
       v                   v            v
  PostgreSQL           Gemini API     Redis  (response cache, sessions, counters, rate limit)
  (SQLAlchemy async)
                           ^
 Celery worker + beat -----+  monitors every 15 min, digest 08:00 UTC, content queue every 5 min
```

## Components

| Module | Responsibility |
|---|---|
| `main.py` | App factory and lifespan (creates tables only in `development`), CORS (open in development, allow-list otherwise), rate-limit middleware, route mounting, serves the SPA at `/` and `/app`, disables `/docs` outside development |
| `core/config` | Pydantic settings from environment; `SECRET_KEY` is required (min 32 chars) |
| `core/db` | Async engine and session (`get_db` commits or rolls back per request); models: `User`, `APIKey`, `BotInstance`, `TaskExecution`, `UsageRecord`, `MonitoredSource`, `MonitoredAlert`, `ConversationSession`, `ProductJob`, `ScheduledProduct` |
| `core/auth` | Password hashing (bcrypt), HS256 JWT access and refresh tokens, API keys stored as SHA-256 hashes with a visible prefix, Google OAuth, plan tiers and limits, `require_plan` dependency |
| `core/api` | Registration, login, profile, API-key management, billing routes |
| `core/gateway` | `AIGateway.complete` and `stream`: picks a model per task type, caches responses in Redis (SHA-256 of model, messages, temperature), falls back to a second model on failure, estimates tokens and cost, records usage |
| `core/cache` | `Cache` (JSON values with TTL, counters), Redis connection, sliding-window `RateLimiter` |
| `core/memory` | `SessionMemory`: per-platform, per-bot, per-user conversation window in Redis (last 20 messages, 7-day TTL) |
| `core/queue` | Celery app and beat schedule |
| `core/services` | Shared search, scraping, document (PDF text), translation (cached) and notification (Telegram, email) services; agents are expected to use these rather than call providers directly |
| `core/tools` | Registry of reusable async tools (`@tool`) such as RSS, Reddit, web fetch, PDF extract, Telegram send, email send |
| `bots/` | Four product bots: Telegram assistant, local-business agent, monitoring, content transformation, each with `router.py`, `agent.py`, `prompts.py` and (where scheduled) `tasks.py` |
| `agents/` | Document, intelligence, political, property, translation agents that implement the multi-product features |
| `products/router.py` | Request models and routes that map each product name to an agent and parameters, plus a `/products/catalog` listing |

## Key flows

**Authenticated request.** JWT bearer or `X-API-Key` -> `get_current_user_flexible` -> route handler. API-key requests are rate limited per key prefix in middleware (sliding window in Redis); JWT requests are not rate limited there.

**LLM call.** Caller supplies messages and a task type (`summarize`, `analyze`, `chat`, ...). The gateway maps the task to a model (lighter model for cheap tasks, stronger for analysis and generation), checks the Redis cache, calls Gemini, retries once with the configured fallback model on error, computes an estimated cost, writes usage counters to Redis and caches the result for an hour.

**Telegram assistant.** Telegram posts to `/telegram/webhook/{bot_id}` -> bot looked up in Postgres -> update handed to a `TelegramAgent` in a background task -> intent detection routes to a specialised prompt (research, summarize, translate, generate, calculate, analyze, chat) -> reply sent via the Bot API; conversation context lives in `SessionMemory`.

**Monitoring.** Celery beat runs `run_all_monitors` every 15 minutes: load active monitoring bots -> fetch each source (RSS, Reddit, web) -> keyword filter -> AI analysis capped per run -> deliver alerts (Telegram, email) -> store `MonitoredAlert`; a daily digest is sent at 08:00 UTC.

**Payments.** Razorpay: create order, then verify an HMAC-SHA256 signature of `order_id|payment_id` before upgrading the plan. PayPal: create order, then capture and upgrade. Sandbox versus live PayPal is a setting.

## Key design decisions

- **Products are configuration over shared agents.** `products/router.py` maps about 30 products onto a handful of shared agents (document, intelligence, political, property, translation) and the content bot, so a new product is a prompt and a route rather than new infrastructure.
- **One gateway for all model calls.** Model choice, caching, fallback and cost tracking live in one place instead of in every bot.
- **Shared services instead of per-agent integrations.** Search, scraping, documents, translation and notifications are single implementations the agents reuse.
- **Redis for hot state, Postgres for durable state.** Sessions, caches, counters and rate limits in Redis; accounts, bots, alerts, jobs and usage records in Postgres.
- **Async end to end.** Async SQLAlchemy, async Redis and httpx so webhook and API handlers do not block on I/O; Celery tasks bridge into async code with `asyncio.run`.
- **Scheduled work out of the request path.** Monitoring and content queues run in Celery workers driven by beat.
- **Hashed credentials.** Passwords with bcrypt, API keys as SHA-256 hashes, payment signatures checked with constant-time comparison.
- **Production hardening switches.** API explorer and OpenAPI schema are disabled and CORS restricted when `ENV` is not `development`.

## Deployment shape

`infra/docker/docker-compose.yml` runs api, worker, beat, Postgres (pgvector image), Redis and Flower on one network. `infra/aws/task-definition.json` defines a Fargate task for the API container; `infra/scripts/deploy.sh` builds, pushes to ECR and forces a new ECS deployment. The worker and beat have no ECS definition in this repo.

## Known limitations

- `core.queue.billing_tasks.rollup_usage` (scheduled nightly) does not exist, so Redis usage counters are never persisted to the database.
- Plan limits other than `require_plan` gating are reported but not enforced; the daily rate limit setting is unused.
- Telegram webhook requests are not authenticated with Telegram's secret token.
- Agent instances are cached in module-level dictionaries per process, so bot configuration changes may not reach already-created agents until restart, and the cache is per worker.
- Token counts are estimated as characters divided by four.
- No `.dockerignore`: images built with `COPY . .` can include a local `.env` and the virtual environment.
- Compose defaults (Postgres password, published ports, unauthenticated Flower) are for development only.
- Only Gemini models are implemented in the gateway; OpenAI and Anthropic keys are configurable but unused there.
- No unit or integration tests; the end-to-end scripts need a running deployment.
