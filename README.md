# Automated Client Scouting & Outreach Engine

An autonomous, semi-supervised client prospecting system engineered for Full-Stack AI Engineers to acquire high-value B2B automation clients with **$0 infrastructure spend**.

The engine automates heavy cognitive lifting—target discovery, JavaScript-rendered web extraction, business bottleneck evaluation, fit scoring, and personalized cold outreach drafting—while enforcing a strict **Dual Human-in-the-Loop (HITL)** mobile control protocol via Telegram before any outbound communication is dispatched.

---

## ⚡ Key Highlights & Zero-Cost Architecture

- **Zero-Cost Discovery**: Unmetered prospect keyword search using `ddgs` (DuckDuckGo) and geographic entity resolution with OpenStreetMap Overpass API ($0.00 / no API billing).
- **Fast Web Extraction**: Headless SPA hydration and automatic noise/boilerplate stripping to clean markdown via `crawl4ai` and `playwright`.
- **Zero-Cost Email Verification**: Direct asynchronous DNS MX lookups with TTL caching and raw socket SMTP mailbox handshakes without burning credits on third-party verification APIs.
- **Intelligent Reasoning & Schema Enforcement**: LiteLLM proxy router leveraging **Gemini 3.7 Flash** (Google AI Studio Free Tier) with automatic fallback to **Llama 3.3 70B Versatile** (Groq Cloud) with strict Pydantic v2 JSON schema enforcement.
- **Dual Mobile HITL Gates (Telegram)**:
  - **Gate 1 (Lead Qualification)**: Push card displaying Fit Score ($1–10$), Operations Summary, 3 Pros, 3 Cons, and Pitch Angle with `[✅ Approve & Draft]` / `[❌ Discard]` buttons.
  - **Gate 2 (Email Review & Edit)**: Push card displaying generated Subject Line & 3-sentence Pitch Body with `[🚀 Confirm & Send]`, `[✏️ Edit Copy]` (direct in-chat reply editing), and `[❌ Cancel]`.
- **Safe Outbox Dispatcher**: Dispatches approved emails via official Gmail API (OAuth2) with 10–25 minute random jitter, business hours validation ($09:00–17:00$), and hard daily volume limits ($5–15$ emails/day).
- **Managed Persistence**: Supabase (PostgreSQL) database with Row-Level Security (RLS) enabled and backend execution via `service_role` key.

---

## 🏗️ System Architecture

```text
                       [ Scheduled Periodic Scouting Runner ]
                                         │
                                         ▼
                 ┌────────────────────────────────────────────────┐
                 │ 1. DISCOVERY & EXTRACTION                      │
                 │ • DuckDuckGo Search (ddgs)                     │
                 │ • OpenStreetMap Overpass API                   │
                 │ • Crawl4AI AsyncWebCrawler (Markdown output)   │
                 └───────────────────────┬────────────────────────┘
                                         │
                                         ▼
                 ┌────────────────────────────────────────────────┐
                 │ 2. CONTACT RESOLUTION & ZERO-COST VERIFICATION │
                 │ • Local Async DNS MX Record Check & TTL Cache  │
                 │ • Direct SMTP Socket Mailbox Handshake         │
                 └───────────────────────┬────────────────────────┘
                                         │
                                         ▼
                 ┌────────────────────────────────────────────────┐
                 │ 3. INTELLIGENCE & EVALUATION LAYER             │
                 │ • LiteLLM Router: Gemini Flash / Groq Llama    │
                 │ • Pydantic v2 Strict Structured Schemas        │
                 └───────────────────────┬────────────────────────┘
                                         │
                                         ▼
                 ┌────────────────────────────────────────────────┐
                 │ 4. PERSISTENCE LAYER (Supabase / Postgres)     │
                 │ • Status: 'PENDING_LEAD_REVIEW'                │
                 └───────────────────────┬────────────────────────┘
                                         │
                                         ▼
                 ┌────────────────────────────────────────────────┐
                 │ 5. MOBILE HITL GATE 1: LEAD REVIEW (Telegram)  │
                 │ • Fit Score, Pros/Cons, Angle Push Card        │
                 │ • [✅ Approve & Draft]  |  [❌ Discard]        │
                 └───────────────┬────────────────┬───────────────┘
                                 │                │
                        [✅ Approve]          [❌ Discard]
                                 │                │
                                 ▼                ▼
                 ┌────────────────────────┐  ┌──────────────────┐
                 │ 6. COPYWRITING ENGINE  │  │ Status:          │
                 │ • 3-sentence cold pitch│  │ 'LEAD_REJECTED'  │
                 └───────────────┬────────┘  └──────────────────┘
                                 │
                                 ▼
                 ┌────────────────────────────────────────────────┐
                 │ 7. MOBILE HITL GATE 2: DRAFT REVIEW (Telegram) │
                 │ • Subject & Body Approval                      │
                 │ • [🚀 Confirm & Send] | [✏️ Edit] | [❌ Cancel] │
                 └───────────────┬────────────────┬───────────────┘
                                 │                │
                        [🚀 Confirm & Send]   [❌ Cancel]
                                 │                │
                                 ▼                ▼
                 ┌────────────────────────┐  ┌──────────────────┐
                 │ 8. OUTBOX DISPATCH     │  │ Status:          │
                 │ • Gmail API (OAuth2)   │  │ 'DRAFT_REJECTED' │
                 │ • 10-25 min jitter     │  └──────────────────┘
                 │ • Status: 'EMAIL_SENT' │
                 └────────────────────────┘
```

---

## 🎯 Target Verticals (ICP)

1. **Logistics & Freight SMBs**: High volume of daily waybills, customs manifests, and manual ERP entry bottlenecks.
2. **Real Estate & Property Management**: Repetitive tenant inquiries, booking friction, and maintenance dispatching.
3. **Boutique Agencies & E-commerce ($500k–$3M ARR)**: Repetitive order processing, inventory sync, and customer support triage.

---

## 📂 Project Structure

```text
client-search/
├── config/
│   ├── settings.py          # Pydantic Settings & environment validation
│   ├── credentials.json     # Gmail OAuth2 client secrets (gitignored)
│   └── token.json           # Stored Gmail user token (gitignored)
├── database/
│   ├── client.py            # Supabase AsyncClient singleton & lifecycle
│   ├── queries.py           # Lead CRUD operations & status transitions
│   └── schema.sql           # PostgreSQL table, enum DDL & RLS rules
├── discovery/
│   ├── searcher.py          # DuckDuckGo & Overpass discovery engine
│   └── crawler.py           # Crawl4AI markdown extraction pipeline
├── evaluators/
│   ├── schemas.py           # Pydantic v2 models (LeadEvaluation, EmailDraft, LeadRecord)
│   └── llm_service.py       # LiteLLM router (Gemini 3.7 Flash + Groq fallback)
├── verification/
│   └── email_verifier.py    # Local async DNS MX & raw SMTP socket verifier
├── bot/
│   ├── telegram_bot.py      # Bot initialization, commands & push cards
│   └── callbacks.py         # Gate 1 & Gate 2 interactive button handlers
├── dispatch/
│   └── gmail_sender.py      # Gmail API OAuth2 dispatch with jitter & volume control
├── tests/                   # 111 Pytest unit and E2E integration tests
├── docs/task-logs/          # Architectural decisions & task reports (Tasks 1-9)
├── scheduler.py             # Periodic background scouting pipeline runner
├── main.py                  # CLI entrypoint & service lifecycle manager
├── requirements.txt         # Pinned production & development dependencies
├── .env.example             # Environment configuration template
└── README.md                # System documentation
```

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.11+ or 3.12+**
- **[uv](https://github.com/astral-sh/uv)** (fast Python package manager)

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/baderGorchene/client-search.git
cd client-search

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# Install Playwright browser binaries
uv run playwright install --with-deps chromium
```

### 3. Environment Configuration

Copy the example environment file and fill in your API credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
TELEGRAM_CHAT_ID="your_personal_telegram_chat_id"

# LLM API Keys (Zero-Cost / Free Tiers)
GEMINI_API_KEY="your_google_ai_studio_api_key"
GROQ_API_KEY="your_groq_api_key"

# Database Configuration (Supabase)
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_KEY="your_supabase_service_role_key"

# Outbound Gmail API Configuration
GMAIL_CREDENTIALS_FILE="config/credentials.json"
GMAIL_TOKEN_FILE="config/token.json"

# Operational Limits & Safety
DAILY_EMAIL_CAP=15
MIN_LEAD_FIT_SCORE=7
EMAIL_JITTER_MIN_SECONDS=600
EMAIL_JITTER_MAX_SECONDS=1500
```

### 4. Database Setup (Supabase)

1. Navigate to the SQL Editor in your [Supabase Dashboard](https://supabase.com/dashboard).
2. Execute the DDL script found in [`database/schema.sql`](file:///home/bunshee/Projects/client-search/database/schema.sql).
3. The table `leads` will be created with Row-Level Security (RLS) enabled and indexed on `status` and `website_url`.

---

## 💻 CLI Usage

The system exposes a unified CLI in `main.py` with subcommands:

### 1. Run Autonomous Service (Scheduler + Telegram Bot)
Starts the recurring background prospecting scheduler and the Telegram HITL bot interface concurrently with clean OS signal handling (`SIGINT`, `SIGTERM`):

```bash
uv run python main.py run --interval 4 --scout-now
```

### 2. One-Shot Prospect Scouting Run
Execute an immediate discovery, extraction, verification, evaluation, and Telegram push cycle for a specific vertical and location without starting the background daemon:

```bash
uv run python main.py scout --vertical logistics --location "Chicago, IL" --limit 5 --min-score 7
```

### 3. Telegram HITL Bot Only
Run only the interactive mobile Telegram interface in polling mode:

```bash
uv run python main.py bot
```

### 4. Check Pipeline Metrics Dashboard
Inspect lead volumes and state distributions across all stages directly in your terminal:

```bash
uv run python main.py status
```

### 5. Dispatch Approved Emails
Send approved drafts waiting in the outbox queue:

```bash
# Dispatch next 5 approved emails with safety jitter
uv run python main.py dispatch --limit 5 --jitter

# Dispatch a specific lead by UUID immediately
uv run python main.py dispatch --lead-id "00000000-0000-0000-0000-000000000000"
```

---

## 📱 Telegram Operator Commands

When interacting with the Telegram Bot:
- `/start` - Displays the system welcome banner and operating status.
- `/status` - Displays live database metrics across all lead statuses and daily outbox caps.
- `/pending` - Lists the top pending Gate 1 (Lead Qualification) and Gate 2 (Draft Approval) review items.
- `/help` - Displays the operator quick reference guide.

---

## 🧪 Verification & Testing

The project includes an end-to-end automated test suite with full async mocking:

```bash
# Run all 111 unit, integration, and E2E tests
uv run pytest

# Run targeted test suites
uv run pytest tests/test_discovery.py
uv run pytest tests/test_crawler.py
uv run pytest tests/test_verifier.py
uv run pytest tests/test_llm_service.py
uv run pytest tests/test_telegram_bot.py
uv run pytest tests/test_gmail_sender.py
uv run pytest tests/test_pipeline_e2e.py

# Lint and formatting validation
uv run ruff check .
```

---

## 🔒 Security & Best Practices

- **Zero API Leakage**: All secrets (`.env`, `credentials.json`, `token.json`) are strictly excluded from git tracking via `.gitignore`.
- **Anti-Spam & Domain Reputation Protection**: Hard daily limits (`DAILY_EMAIL_CAP=15`) with mandatory dual human verification prevents rogue or runaway dispatches.
- **Row-Level Security**: Production database restricts unauthorized anonymous public access while permitting server-side backend operations via `service_role`.
