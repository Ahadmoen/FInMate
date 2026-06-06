-- Run this in Supabase SQL Editor:
-- Dashboard → SQL Editor → New query → paste → Run

-- 1. Allow the stock_symbol table to be read by anon
GRANT SELECT ON stock_symbol TO anon;

-- 2. Enable RLS on portfolio_holdings
ALTER TABLE portfolio_holdings ENABLE ROW LEVEL SECURITY;

-- 3. Dev policy — lets the anon key read all holdings
DROP POLICY IF EXISTS "anon_read_all_dev" ON portfolio_holdings;
CREATE POLICY "anon_read_all_dev" ON portfolio_holdings
    FOR SELECT TO anon USING (true);

-- 4. Grant SELECT at the table level
GRANT SELECT ON portfolio_holdings TO anon;
