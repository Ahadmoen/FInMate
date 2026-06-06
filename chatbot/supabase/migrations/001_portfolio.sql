-- Migration 001: Portfolio tables
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New query)
-- or via: psql $SUPABASE_DB_URL -f supabase/migrations/001_portfolio.sql

-- ── symbols ───────────────────────────────────────────────────────────────────
-- Maps a stable UUID to a PSX ticker string.
-- portfolio_holdings references this table via symbol_id.

CREATE TABLE IF NOT EXISTS symbols (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker       TEXT NOT NULL UNIQUE,
    company_name TEXT,
    sector       TEXT,
    exchange     TEXT NOT NULL DEFAULT 'PSX',
    is_active    BOOLEAN NOT NULL DEFAULT true,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed all PSX tickers that the app already knows about
INSERT INTO symbols (ticker, company_name, sector) VALUES
    ('PSO',    'Pakistan State Oil',            'Energy'),
    ('NBP',    'National Bank of Pakistan',     'Banking'),
    ('FFC',    'Fauji Fertilizer Company',      'Fertilizers'),
    ('ENGRO',  'Engro Corporation',             'Diversified'),
    ('OGDC',   'Oil & Gas Development Company', 'Energy'),
    ('PPL',    'Pakistan Petroleum Limited',    'Energy'),
    ('HBL',    'Habib Bank Limited',            'Banking'),
    ('MCB',    'MCB Bank Limited',              'Banking'),
    ('UBL',    'United Bank Limited',           'Banking'),
    ('LUCK',   'Lucky Cement',                  'Cement'),
    ('EFERT',  'Engro Fertilizers',             'Fertilizers'),
    ('HUBC',   'Hub Power Company',             'Power'),
    ('KAPCO',  'Kot Addu Power Company',        'Power'),
    ('KEL',    'K-Electric Limited',            'Power'),
    ('MARI',   'Mari Petroleum Company',        'Energy'),
    ('POL',    'Pakistan Oilfields Limited',    'Energy'),
    ('TRG',    'TRG Pakistan Limited',          'Technology'),
    ('SYS',    'Systems Limited',               'Technology'),
    ('NETSOL', 'NetSol Technologies',           'Technology'),
    ('UNITY',  'Unity Foods',                   'Consumer'),
    ('BAHL',   'Bank AL Habib',                 'Banking'),
    ('MEBL',   'Meezan Bank',                   'Banking'),
    ('FABL',   'Faysal Bank',                   'Banking'),
    ('SILK',   'Silkbank',                      'Banking'),
    ('PIOC',   'Pioneer Cement',                'Cement'),
    ('MLCF',   'Maple Leaf Cement',             'Cement'),
    ('CHCC',   'Cherat Cement',                 'Cement'),
    ('DGKC',   'DG Khan Cement',                'Cement'),
    ('MUGHAL', 'Mughal Iron & Steel',           'Steel'),
    ('SSGC',   'Sui Southern Gas Company',      'Energy'),
    ('SINDM',  'Sindh Modaraba',                'Financial'),
    ('WHALE',  'Whale Industries',              'Industrial'),
    ('CYAN',   'Cyan Limited',                  'Diversified'),
    ('META',   'Meta Holdings',                 'Diversified')
ON CONFLICT (ticker) DO UPDATE SET
    company_name = EXCLUDED.company_name,
    sector       = EXCLUDED.sector;

-- ── portfolio_holdings ────────────────────────────────────────────────────────
-- One row per (user, symbol). quantity and avg_buy_price are updated on each
-- buy/sell rather than storing individual trade legs.

CREATE TABLE IF NOT EXISTS portfolio_holdings (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL,   -- references auth.users(id) in Supabase Auth
    symbol_id     UUID NOT NULL REFERENCES symbols(id) ON DELETE RESTRICT,
    quantity      NUMERIC(20, 4) NOT NULL CHECK (quantity > 0),
    avg_buy_price NUMERIC(20, 4) NOT NULL CHECK (avg_buy_price > 0),
    added_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, symbol_id)
);

-- Index for fast per-user lookups
CREATE INDEX IF NOT EXISTS idx_portfolio_holdings_user_id
    ON portfolio_holdings (user_id);

-- Auto-update updated_at on every row change
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_portfolio_holdings_updated_at ON portfolio_holdings;
CREATE TRIGGER trg_portfolio_holdings_updated_at
    BEFORE UPDATE ON portfolio_holdings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── Permissions ───────────────────────────────────────────────────────────────
-- Grant SELECT on symbols to the anon role (read-only ticker reference data)
GRANT SELECT ON symbols TO anon;

-- portfolio_holdings — enable RLS and add policies
ALTER TABLE portfolio_holdings ENABLE ROW LEVEL SECURITY;

-- Policy 1 (production): users can only see their own holdings via Supabase Auth JWT
-- Uncomment this when using Supabase Auth on the frontend:
-- CREATE POLICY "users_own_holdings" ON portfolio_holdings
--     FOR ALL TO authenticated USING (auth.uid() = user_id);

-- Policy 2 (development / server-side): allow the service role (used by backend)
-- The service role bypasses RLS by default in Supabase — no policy needed for it.

-- Policy 3 (development only — NOT for production): allow anon to read all holdings
-- Remove this and use Policy 1 once Supabase Auth is wired up on the frontend:
CREATE POLICY "anon_read_all_dev" ON portfolio_holdings
    FOR SELECT TO anon USING (true);

-- Also needed: grant SELECT to the anon role at the table level
GRANT SELECT ON portfolio_holdings TO anon;
