# Development Roadmap

- [x] **Task 1: Environment & Project Foundation Setup**
  - Objective: Initialize project configuration, `.env.example`, `requirements.txt`, and `config/settings.py` with Pydantic Settings.
  - Verification: `uv run python -c "from config.settings import settings; print('Settings loaded')"`
  - Status: Completed

- [x] **Task 2: Pydantic Data Models & Database Layer**
  - Objective: Implement `evaluators/schemas.py` (`LeadEvaluation`, `EmailDraft`) and `database/client.py` / `database/queries.py` for Supabase/PostgreSQL schema and CRUD.
  - Verification: `uv run pytest tests/test_database.py`
  - Status: Completed

- [x] **Task 3: Zero-Cost Discovery Engine (DuckDuckGo & Overpass)**
  - Objective: Implement `discovery/searcher.py` using `duckduckgo-search` and OpenStreetMap Overpass API for targeted ICP vertical queries.
  - Verification: `uv run pytest tests/test_searcher.py`
  - Status: Completed

- [x] **Task 4: Web Extraction Pipeline (Crawl4AI)**
  - Objective: Implement `discovery/crawler.py` using Crawl4AI `AsyncWebCrawler` with SPA hydration and boilerplate/noise stripping to markdown.
  - Verification: `uv run pytest tests/test_crawler.py`
  - Status: Completed

- [x] **Task 5: Zero-Cost Email Resolution & Verification Gate**
  - Objective: Implement `verification/email_verifier.py` with async DNS MX validation and direct SMTP socket handshake checks.
  - Verification: `uv run pytest tests/test_verifier.py`
  - Status: Completed

- [x] **Task 6: Intelligence & Copywriting LLM Router**
  - Objective: Implement `evaluators/llm_service.py` with LiteLLM routing (Gemini 3.7 Flash primary, Groq Llama 3.3 fallback) and strict structured schema enforcement.
  - Verification: `uv run pytest tests/test_llm_service.py`
  - Status: Completed

- [x] **Task 7: Mobile HITL Telegram Bot (Gate 1 & Gate 2)**
  - Objective: Implement `bot/telegram_bot.py` and `bot/callbacks.py` supporting Gate 1 (Lead qualification) and Gate 2 (Draft approval/editing) inline actions.
  - Verification: `uv run pytest tests/test_telegram_bot.py`
  - Status: Completed

- [x] **Task 8: Outbox Dispatcher with Rate Limiting & Safety Jitter**
  - Objective: Implement `dispatch/gmail_sender.py` with Gmail API OAuth2 integration, 10–25 minute random jitter, and daily email volume capping.
  - Verification: `uv run pytest tests/test_gmail_sender.py`
  - Status: Completed

- [x] **Task 9: Pipeline Orchestration, Scheduler & E2E Integration**
  - Objective: Wire end-to-end pipeline in `scheduler.py` (APScheduler) and `main.py` entrypoint with graceful shutdown and end-to-end testing.
  - Verification: `uv run pytest tests/test_pipeline_e2e.py`
  - Status: Completed

- [ ] **Task 10: Interactive Web Dashboard with Reflex**
  - Objective: Implement pure-Python reactive web dashboard using Reflex (`ui/`, `rxconfig.py`) featuring live pipeline Kanban boards (Gate 1 & Gate 2), scouting trigger controls, email preview/editor, and metrics dashboard linked to Supabase.
  - Verification: `uv run python -c "import reflex; print('Reflex ready')"` and `uv run pytest tests/test_ui.py`
  - Status: Pending
