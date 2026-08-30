# Automated Client Scouting & Outreach Engine (Complete Technical Blueprint)

## 1\. Executive Summary & Objective

An autonomous, semi-supervised client prospecting system engineered for a Full-Stack AI Engineer to acquire high-value B2B automation clients with **$0 infrastructure spend**.

The system automates the heavy cognitive lifting—target discovery, dynamic web crawling, business bottleneck analysis, fit evaluation (pros/cons), and personalized cold outreach drafting—while enforcing a strict **Dual Human-in-the-Loop (HITL)** mobile control protocol via Telegram before any message is dispatched.

---

## 2\. Positioning & Ideal Customer Profile (ICP)

* **Core Offer:** Productized Workflow Automation (e.g., Unstructured Invoice/Paperwork OCR Extraction Pipelines, Real-Time Voice/Chat Inbound Booking Agents, Custom Internal Operations Dashboards).  
* **Target Verticals:**  
  * **Logistics & Freight SMBs:** High volume of daily waybills, customs manifests, and manual ERP entry bottlenecks.  
  * **Real Estate & Property Management:** Repetitive tenant inquiries, booking friction, and maintenance dispatching.  
  * **Boutique Agencies & E-commerce ($500k–$3M ARR):** Repetitive order processing, inventory sync, and customer support triage.  
* **Disqualified Targets:** Cash-strapped micro-businesses, companies without websites, or non-digital local kiosks.

---

## 3\. End-to-End System Architecture

                                \[Scheduled 1-Hour Scouting Run\]

                                                │

                                                ▼

              ┌──────────────────────────────────────────────────────────────────┐

              │ 1\. DISCOVERY & EXTRACTION LAYER                                  │

              │ • duckduckgo-search / Overpass API (Zero-Cost Keyword Search)    │

              │ • Crawl4AI AsyncWebCrawler (SPA hydration & noise stripping)    │

              └────────────────────────────────┬─────────────────────────────────┘

                                                │

                                                ▼

              ┌──────────────────────────────────────────────────────────────────┐

              │ 2\. CONTACT RESOLUTION & ZERO-COST VERIFICATION                   │

              │ • Local Async DNS MX Record Check \+ Raw SMTP Socket Handshake    │

              │ • Pattern Generator (first.last@domain) \+ Apollo Free API        │

              └────────────────────────────────┬─────────────────────────────────┘

                                                │

                                                ▼

              ┌──────────────────────────────────────────────────────────────────┐

              │ 3\. INTELLIGENCE & EVALUATION LAYER                               │

              │ • LiteLLM Router:                                                │

              │   ├── Primary: Gemini 3.5 Flash (Google AI Studio)               │

              │   └── Fallback: Gemini 3.5 Flash-Lite (Google AI Studio)         │

              │ • Strict Pydantic v2 Schema Fit Scoring & Bottleneck Extraction  │

              └────────────────────────────────┬─────────────────────────────────┘

                                                │

                                                ▼

              ┌──────────────────────────────────────────────────────────────────┐

              │ 4\. PERSISTENCE LAYER                                             │

              │ • Supabase (PostgreSQL) \-\> Status: 'PENDING\_LEAD\_REVIEW'         │

              └────────────────────────────────┬─────────────────────────────────┘

                                                │

                                                ▼

              ┌──────────────────────────────────────────────────────────────────┐

              │ 5\. MOBILE HITL GATE 1: LEAD QUALIFICATION (Telegram Bot)        │

              │ • Push Card: Fit Score (1-10), 3 Pros, 3 Cons, Pitch Angle       │

              │ • Actions: \[✅ Approve & Draft\] | \[❌ Discard\]                    │

              └────────────────┬───────────────────────────────┬─────────────────┘

                               │                               │

                    \[✅ Approve Lead\]                     \[❌ Discard\]

                               │                               │

                               ▼                               ▼

              ┌─────────────────────────────────┐     ┌─────────────────┐

              │ 6\. COPYWRITING ENGINE (LLM)     │     │ Status:         │

              │ • 3-sentence value-driven draft │     │ 'LEAD\_REJECTED' │

              └────────────────┬────────────────┘     └─────────────────┘

                               │

                               ▼

              ┌──────────────────────────────────────────────────────────────────┐

              │ 7\. MOBILE HITL GATE 2: DRAFT APPROVAL (Telegram Bot)             │

              │ • Displays Generated Subject & Body                              │

              │ • Actions: \[🚀 Confirm & Send\] | \[✏️ Edit Copy\] | \[❌ Cancel\]     │

              └────────────────┬───────────────────────────────┬─────────────────┘

                               │                               │

                  \[🚀 Confirm & Send\]                     \[❌ Cancel\]

                               │                               │

                               ▼                               ▼

              ┌─────────────────────────────────┐     ┌─────────────────┐

              │ 8\. OUTBOX DISPATCH              │     │ Status:         │

              │ • Gmail API (OAuth2)            │     │ 'DRAFT\_ARCHIVED'│

              │ • Status: 'EMAIL\_SENT'          │     └─────────────────┘

              └─────────────────────────────────┘

---

## 4\. Subsystem Technical Specifications

### Subsystem 1: Lead Discovery & Extraction (`discovery/`)

* **Discovery Engine (`searcher.py`):** Uses `duckduckgo-search` and OpenStreetMap Overpass API for unmetered, zero-cost keyword and geographic company discovery without API keys.  
* **Extraction Engine (`crawler.py`):** Uses [**Crawl4AI**](https://docs.crawl4ai.com/) (`AsyncWebCrawler`).  
  * Automatically removes boilerplate, cookie banners, navigation menus, and tracking scripts.  
  * Hydrates client-side JavaScript SPAs into clean, LLM-ready markdown (\<1,500 tokens).

### Subsystem 2: Contact Discovery & Zero-Cost Verification (`verification/`)

* **Resolution Pipeline:** Scans `/contact`, `/team`, `/about`, and footer elements for direct emails and executive names; falls back to standard permutations (`first.last@domain.com`).  
* **Verification Gate (`email_verifier.py`):** Uses [**`py3-validate-email`](https://socket.dev/pypi/category/utilities/security/email-validation)**.  
  * Queries domain MX records via DNS.  
  * Performs an asynchronous socket handshake with the recipient mail server to confirm mailbox existence for $0.00 without burning third-party API credits.

### Subsystem 3: Evaluation & Intelligence Engine (`evaluators/`)

* **Router Layer (`llm_service.py`):** [**LiteLLM**](https://www.getmaxim.ai/articles/openrouter-vs-litellm-vs-bifrost-multi-provider-llm-access/) unified Python proxy router.  
  * **Primary Model:** [**Gemini 3.5 Flash**](https://ai.google.dev/gemini-api/docs/pricing) via Google AI Studio Free Tier (unrivaled 1M+ token context and strict Pydantic JSON adherence).  
  * **Fallback Model:** [**Gemini 3.5 Flash-Lite**](https://ai.google.dev/gemini-api/docs/pricing) via Google AI Studio Free Tier (high throughput, low latency backup).  
* **Pydantic v2 Validation Schemas (`schemas.py`):**  
    
  from pydantic import BaseModel, Field  
    
  from typing import List  
    
  class LeadEvaluation(BaseModel):  
    
      company\_name: str  
    
      website\_url: str  
    
      decision\_maker\_name: str  
    
      decision\_maker\_title: str  
    
      decision\_maker\_email: str  
    
      fit\_score: int \= Field(..., ge=1, le=10, description="Fit score from 1-10")  
    
      summary: str \= Field(..., max\_length=250, description="Company operations summary")  
    
      pros: List\[str\] \= Field(..., max\_items=3, description="Key workflow bottlenecks suitable for automation")  
    
      cons: List\[str\] \= Field(..., max\_items=3, description="Potential friction points or risks")  
    
      suggested\_angle: str \= Field(..., max\_length=150, description="Specific pitch hook")  
    
  class EmailDraft(BaseModel):  
    
      subject: str \= Field(..., max\_length=50, description="Short, lowercase, punchy subject")  
    
      body: str \= Field(..., max\_length=600, description="3-sentence value-driven cold pitch")

### Subsystem 4: Mobile HITL Interface (`bot/`)

* **Framework:** `python-telegram-bot` v21+ (asyncio).  
* **Gate 1 (Lead Review):** Pushes an interactive card displaying the lead score, pros, cons, and suggested angle with inline buttons `[✅ Approve & Draft]` and `[❌ Discard]`.  
* **Gate 2 (Email Draft Review):** Pushes the generated subject line and body with `[🚀 Confirm & Send]`, `[✏️ Edit Copy]`, and `[❌ Cancel]`.

### Subsystem 5: Outbox Dispatch & Protection (`dispatch/`)

* **Provider (`gmail_sender.py`):** Gmail API via OAuth2 user credentials.  
* **Volume Cap:** Strictly limited to **5 to 15 hand-approved emails/day**.  
* **Sending Pacing:** Random jitter (10–25 minutes) between approved dispatches during target business hours (09:00–17:00).

### Subsystem 6: Interactive Operations & Analytics Dashboard (`ui/`)

* **Framework:** [**Reflex**](https://reflex.dev/) (Pure-Python reactive web framework with compiled Next.js/Tailwind frontend).  
* **Pipeline Kanban & Review Board:** Real-time visual tracking of leads across all stages (`PENDING_LEAD_REVIEW`, `DRAFT_GENERATED`, `EMAIL_SENT`, `REPLIED_INTERESTED`, `LEAD_REJECTED`, `DRAFT_REJECTED`).  
* **Interactive Operations:**  
  * Trigger immediate one-shot scouting cycles with custom vertical and geographic parameters.  
  * Manual review & qualification of Gate 1 leads with pros/cons breakdown and score adjustments.  
  * Rich draft editor to review, edit, and approve Gate 2 cold pitches before dispatch.  
  * Real-time KPI charts and deliverability health metrics linked to Supabase.

---

## 5\. PostgreSQL / Supabase Database Schema

CREATE TYPE lead\_status AS ENUM (

    'PENDING\_LEAD\_REVIEW',

    'LEAD\_REJECTED',

    'DRAFT\_GENERATED',

    'DRAFT\_REJECTED',

    'EMAIL\_SENT',

    'REPLIED\_INTERESTED',

    'REPLIED\_NOT\_INTERESTED'

);

CREATE TABLE leads (

    id UUID PRIMARY KEY DEFAULT gen\_random\_uuid(),

    company\_name TEXT NOT NULL,

    website\_url TEXT NOT NULL UNIQUE,

    decision\_maker\_name TEXT,

    decision\_maker\_title TEXT,

    decision\_maker\_email TEXT,

    fit\_score INT CHECK (fit\_score BETWEEN 1 AND 10),

    summary TEXT,

    pros JSONB,

    cons JSONB,

    suggested\_angle TEXT,

    email\_subject TEXT,

    email\_body TEXT,

    status lead\_status DEFAULT 'PENDING\_LEAD\_REVIEW',

    telegram\_message\_id BIGINT,

    created\_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    updated\_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()

);

CREATE INDEX idx\_leads\_status ON leads(status);

---

## 6\. Project Directory & Module Architecture

client\_scouting\_engine/

│

├── config/

│   ├── settings.py              # Environment variables & API keys

│   └── logging.py               # Centralized Loguru logger setup & interceptor

│

├── database/

│   ├── client.py                \# Supabase/PostgreSQL connection pool

│   └── queries.py               \# CRUD operations for leads & status updates

│

├── discovery/

│   ├── searcher.py              \# DuckDuckGo / Overpass geo queries

│   └── crawler.py               \# Crawl4AI async extraction pipeline

│

├── evaluators/

│   ├── schemas.py               \# Pydantic v2 data models

│   └── llm\_service.py           \# LiteLLM router (Gemini 3.5 Flash \+ 3.5 Flash-Lite)

│

├── verification/

│   └── email\_verifier.py        \# Local async DNS MX & SMTP socket validator

│

├── bot/

│   ├── telegram\_bot.py          \# Bot initialization & command handlers

│   └── callbacks.py             \# Gate 1 & Gate 2 interactive button logic

│

├── dispatch/

│   └── gmail\_sender.py          \# Gmail API OAuth2 dispatch with jitter

│

├── ui/                          \# Reflex pure-Python web application

│   ├── components/              \# Kanban cards, metric badges, charts

│   ├── pages/                   # Dashboard, pipeline review, settings

│   └── state.py                 \# Reactive state & async event handlers

│

├── rxconfig.py                  \# Reflex configuration

├── scheduler.py                 \# APScheduler loop / background runner

├── main.py                      \# Application entry point & CLI manager

├── .env.example                 \# Config template

└── requirements.txt

---

## 7\. Complete Dependency Specification (`requirements.txt`)

\# Web Scraping & Discovery

crawl4ai\>=0.9.2

playwright\>=1.49.0

duckduckgo-search\>=6.2.0

beautifulsoup4\>=4.12.3

\# LLM Gateway & Validation

litellm\>=1.52.0

google-genai\>=0.1.1

pydantic\>=2.10.0

\# Telegram Bot Interface

python-telegram-bot\[http2\]\>=21.9

\# Web UI & Dashboard

reflex\>=0.7.0

\# Database & Async Client

supabase\>=2.10.0

asyncpg\>=0.30.0

\# Email Deliverability & Dispatch

py3-validate-email\>=1.0.8

dnspython\>=2.7.0

google-api-python-client\>=2.154.0

google-auth-httplib2\>=0.2.0

google-auth-oauthlib\>=1.2.1

\# Scheduling & Utilities

apscheduler>=3.10.4

python-dotenv>=1.0.1

httpx>=0.28.0

loguru>=0.7.3

---

## 8\. Environment Configuration (`.env.example`)

\# Telegram Bot Configuration

TELEGRAM\_BOT\_TOKEN="your\_telegram\_bot\_token"

TELEGRAM\_CHAT\_ID="your\_personal\_telegram\_chat\_id"

\# LLM API Keys

GEMINI\_API\_KEY="your\_google\_ai\_studio\_api\_key"

GROQ\_API\_KEY="your\_groq\_api\_key"

\# Database Configuration (Supabase)

SUPABASE\_URL="https://your-project.supabase.co"

SUPABASE\_KEY="your\_supabase\_service\_role\_key"

\# Outbound Gmail API Configuration

GMAIL\_CREDENTIALS\_FILE="config/credentials.json"

GMAIL\_TOKEN\_FILE="config/token.json"

\# Operational Limits

DAILY\_EMAIL\_CAP=15

MIN\_LEAD\_FIT\_SCORE=7

---

## 9\. Comparative Architecture SOTA Benchmark

| Layer | Chosen Tool | Top Alternative | Why Chosen |
| :---- | :---- | :---- | :---- |
| **LLM Inference** | **Gemini 3.5 Flash** | Gemini 3.5 Flash-Lite | Ingests entire websites (1M+ context) with strict native JSON mode for $0. |
| **Web Extraction** | **Crawl4AI** | Firecrawl / Playwright | Strips HTML boilerplate directly into clean markdown for LLMs without cloud credits. |
| **Lead Discovery** | **`duckduckgo-search`** | Paid SerpAPI | Unmetered keyword search without credit caps or billing requirements. |
| **HITL Controller** | **Telegram Bot** | Next.js Dashboard | Instant lock-screen mobile push approvals; zero frontend hosting required. |
| **Web UI Dashboard** | **Reflex (Pure Python)** | Custom React / Streamlit | Full-stack reactive web apps entirely in Python without frontend toolchain overhead. |
| **Verification** | **`py3-validate-email`** | Paid NeverBounce | Local async SMTP socket handshake verifies mailbox existence for $0.00. |
| **Database** | **Supabase (Postgres)** | Local SQLite | Managed PostgreSQL cloud database with visual dashboard accessible from anywhere. |
| **Architecture** | **Modular Monolith** | Microservices | Zero inter-service network latency, single process, $0 hosting cost, easy local debugging. |
