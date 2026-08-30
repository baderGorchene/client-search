# AGENTS.md

## Tech Stack & Conventions
- **Language**: Python 3.12+ (AsyncIO first)
- **Package Management**: `uv` / standard virtualenv
- **Web Crawling & Discovery**: `crawl4ai` (AsyncWebCrawler), `duckduckgo-search`, `playwright`
- **LLM Gateway & Schemas**: `litellm` (Gemini 3.7 Flash primary, Groq Llama 3.3 70B fallback), `pydantic` v2
- **Telegram HITL Interface**: `python-telegram-bot` (v21+ async handlers & inline keyboards)
- **Web UI & Operations Dashboard**: `reflex` (Pure Python reactive web apps & Tailwind components)
- **Database & Storage**: `supabase` (PostgreSQL async queries & connection pooling)
- **Email Verification & Dispatch**: `py3-validate-email`, `dnspython`, `google-api-python-client` (Gmail API OAuth2)
- **Scheduling**: `apscheduler`
- **Coding Conventions**:
  - Strict type hints with Pydantic v2 schemas for all structured LLM IO and data transfer objects.
  - Fully asynchronous I/O (`async`/`await`) across web scraping, LLM calls, DB queries, and Telegram callbacks.
  - Zero-cost architecture: unmetered APIs (DuckDuckGo, Crawl4AI local markdown, DNS MX handshake) prioritized.

## Project Structure
```text
.
├── config/
│   └── settings.py          # Pydantic Settings / environment variables
├── database/
│   ├── client.py            # Supabase / PostgreSQL async connection pool
│   └── queries.py           # Lead CRUD operations and status transitions
├── discovery/
│   ├── searcher.py          # DuckDuckGo and Overpass geo search engine
│   └── crawler.py           # Crawl4AI markdown extraction and noise stripping
├── evaluators/
│   ├── schemas.py           # Pydantic v2 data models (LeadEvaluation, EmailDraft)
│   └── llm_service.py       # LiteLLM router (Gemini 3.7 Flash + Groq fallback)
├── verification/
│   └── email_verifier.py    # Local async DNS MX & raw SMTP socket verifier
├── bot/
│   ├── telegram_bot.py      # Bot initialization, commands, and notification pushes
│   └── callbacks.py         # Gate 1 (Lead Review) & Gate 2 (Draft Review) handlers
├── dispatch/
│   └── gmail_sender.py      # Gmail API OAuth2 dispatch with jitter & volume control
├── ui/                      # Reflex reactive web application & operator dashboard
│   ├── components/          # Reusable UI cards, tables, and metric badges
│   ├── state.py             # Reflex reactive state and event handlers
│   └── pages/               # Dashboard, Leads review, and Settings views
├── rxconfig.py              # Reflex application configuration
├── tests/                   # Pytest test suite with mocks
├── scheduler.py             # Periodic background scouting pipeline runner
├── main.py                  # CLI entrypoint & service lifecycle manager
├── CONTEXT.md               # Complete technical blueprint specification
├── requirements.txt         # Project dependencies
└── .env.example             # Environment configuration template
```

## Verification Commands
- **Environment Setup**: `uv venv && source .venv/bin/activate && uv pip install -r requirements.txt`
- **Playwright Setup**: `uv run playwright install --with-deps chromium`
- **Run Unit & Integration Tests**: `uv run pytest`
- **Run Targeted Test**: `uv run pytest tests/test_discovery.py`
- **Run Reflex Web UI**: `uv run reflex run`
- **Lint & Format**: `uv run ruff check .`

## Context Boundaries
- **Restricted / Sensitive Files**:
  - `.env`, `.env.local`, `.env.*`
  - `config/credentials.json`, `config/token.json` (Gmail OAuth secrets)
  - Any raw API keys (Gemini, Groq, Supabase, Telegram)
- **Do Not Modify**:
  - Production database schema migrations without explicit verification steps.
