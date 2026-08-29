-- Schema migration for Supabase / PostgreSQL
-- Table: leads
-- Enum: lead_status

CREATE TYPE lead_status AS ENUM (
    'PENDING_LEAD_REVIEW',
    'LEAD_REJECTED',
    'DRAFT_GENERATED',
    'DRAFT_REJECTED',
    'EMAIL_SENT',
    'REPLIED_INTERESTED',
    'REPLIED_NOT_INTERESTED'
);

CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name TEXT NOT NULL,
    website_url TEXT NOT NULL UNIQUE,
    decision_maker_name TEXT,
    decision_maker_title TEXT,
    decision_maker_email TEXT,
    fit_score INT CHECK (fit_score BETWEEN 1 AND 10),
    summary TEXT,
    pros JSONB,
    cons JSONB,
    suggested_angle TEXT,
    email_subject TEXT,
    email_body TEXT,
    status lead_status DEFAULT 'PENDING_LEAD_REVIEW',
    telegram_message_id BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_website_url ON leads(website_url);

-- Enable Row Level Security (RLS)
-- Recommended: Keep RLS enabled. Since this engine operates as a backend service
-- using the Supabase `service_role` key, it automatically bypasses RLS while protecting
-- your leads from unauthorized public `anon` access.
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
