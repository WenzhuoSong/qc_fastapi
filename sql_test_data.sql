-- =========================================================================
-- Phase 2 Week 1 - SQL Test Data & Validation Queries
-- =========================================================================
-- Usage: Copy-paste these queries into Railway PostgreSQL console
--        or execute via: psql $DATABASE_URL < sql_test_data.sql
-- =========================================================================

-- ─────────────────────────────────────────────────────────────────────────
-- SECTION 1: Verify Table Creation
-- ─────────────────────────────────────────────────────────────────────────

-- Check if event_transmission table exists
SELECT EXISTS (
    SELECT FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name = 'event_transmission'
) AS table_exists;
-- Expected: t (true)

-- View table structure
\d event_transmission

-- Count existing records (should be 0 initially)
SELECT COUNT(*) as record_count FROM event_transmission;

-- ─────────────────────────────────────────────────────────────────────────
-- SECTION 2: Insert Test Data
-- ─────────────────────────────────────────────────────────────────────────

-- Test Data 1: 2026-03-20 Iran War + Oil Crisis (Historical)
INSERT INTO event_transmission (
    date,
    event_id,
    event_type,
    event_description,
    confidence,
    transmission_vector,
    validated
) VALUES (
    '2026-03-20',
    'macro_2026-03-20',
    'supply_shock_oil',
    'Iran war escalation with Strait of Hormuz closure threat causing oil supply disruption',
    85,
    '{"XLE": 1.0, "XLY": -1.0, "XLI": 1.0, "XLK": -0.95, "XLF": -0.8, "XLB": 1.0, "XLP": -0.7, "XLV": -0.55, "XLU": -0.9, "XLC": -0.75, "XLRE": -1.0}'::jsonb,
    false
)
ON CONFLICT (event_id) DO NOTHING;
-- Note: ON CONFLICT prevents duplicate inserts if running multiple times

-- Test Data 2: 2026-03-15 Fed Rate Hike
INSERT INTO event_transmission (
    date,
    event_id,
    event_type,
    event_description,
    confidence,
    transmission_vector,
    validated
) VALUES (
    '2026-03-15',
    'macro_2026-03-15',
    'rate_shock_hawkish',
    'Fed hikes 75bps to 5.5%, Powell signals higher for longer policy stance',
    90,
    '{"XLF": 0.7, "XLE": 0.3, "XLB": 0.2, "XLI": 0.1, "XLV": 0.1, "XLP": -0.1, "XLC": -0.4, "XLY": -0.5, "XLU": -0.6, "XLK": -0.8, "XLRE": -0.9}'::jsonb,
    false
)
ON CONFLICT (event_id) DO NOTHING;

-- Test Data 3: 2026-03-10 Risk-Off Credit Stress
INSERT INTO event_transmission (
    date,
    event_id,
    event_type,
    event_description,
    confidence,
    transmission_vector,
    validated
) VALUES (
    '2026-03-10',
    'macro_2026-03-10',
    'risk_off_credit_stress',
    'Regional bank failures trigger credit stress with VIX spiking to 45',
    80,
    '{"XLV": 0.85, "XLP": 0.8, "XLU": 0.7, "XLB": -0.4, "XLI": -0.4, "XLRE": -0.6, "XLC": -0.5, "XLF": -0.7, "XLK": -0.7, "XLY": -0.85}'::jsonb,
    false
)
ON CONFLICT (event_id) DO NOTHING;

-- Test Data 4: 2026-03-05 Fed Dovish Pivot
INSERT INTO event_transmission (
    date,
    event_id,
    event_type,
    event_description,
    confidence,
    transmission_vector,
    validated
) VALUES (
    '2026-03-05',
    'macro_2026-03-05',
    'fed_dovish_easing',
    'Fed pivots dovish with surprise 50bps rate cut and QE announcement',
    75,
    '{"XLRE": 0.8, "XLK": 0.7, "XLU": 0.7, "XLY": 0.6, "XLC": 0.4, "XLF": 0.4, "XLI": 0.3, "XLV": 0.2, "XLP": 0.1, "XLB": -0.2, "XLE": -0.3}'::jsonb,
    false
)
ON CONFLICT (event_id) DO NOTHING;

-- Test Data 5: 2026-02-28 Recession Warning
INSERT INTO event_transmission (
    date,
    event_id,
    event_type,
    event_description,
    confidence,
    transmission_vector,
    validated
) VALUES (
    '2026-02-28',
    'macro_2026-02-28',
    'recession_demand_collapse',
    'GDP contracts -2%, mass layoffs announced, PMI hits 40',
    85,
    '{"XLV": 0.75, "XLP": 0.7, "XLU": 0.6, "XLI": -0.6, "XLE": -0.6, "XLF": -0.5, "XLB": -0.5, "XLK": -0.4, "XLRE": -0.4, "XLC": -0.3, "XLY": -0.8}'::jsonb,
    false
)
ON CONFLICT (event_id) DO NOTHING;

-- Test Data 6: 2026-02-20 War Geopolitical
INSERT INTO event_transmission (
    date,
    event_id,
    event_type,
    event_description,
    confidence,
    transmission_vector,
    validated
) VALUES (
    '2026-02-20',
    'macro_2026-02-20',
    'war_geopolitical',
    'Russia-Ukraine conflict escalates with missile attacks on critical infrastructure',
    80,
    '{"XLI": 0.9, "XLE": 0.8, "XLB": 0.5, "XLV": 0.3, "XLP": 0.25, "XLU": 0.2, "XLC": -0.35, "XLRE": -0.4, "XLK": -0.45, "XLF": -0.5, "XLY": -0.7}'::jsonb,
    false
)
ON CONFLICT (event_id) DO NOTHING;

-- Verify inserts
SELECT COUNT(*) as total_records FROM event_transmission;
-- Expected: 6

-- ─────────────────────────────────────────────────────────────────────────
-- SECTION 3: Basic Validation Queries
-- ─────────────────────────────────────────────────────────────────────────

-- Query 1: View all test data
SELECT
    date,
    event_id,
    event_type,
    confidence,
    LEFT(event_description, 50) as description_preview
FROM event_transmission
ORDER BY date DESC;

-- Query 2: Check transmission vector for 2026-03-20
SELECT
    date,
    event_type,
    transmission_vector->>'XLE' as xle,
    transmission_vector->>'XLY' as xly,
    transmission_vector->>'XLI' as xli
FROM event_transmission
WHERE date = '2026-03-20';
-- Expected: XLE=1.0, XLY=-1.0, XLI=1.0

-- Query 3: Verify all vectors have 11 sectors
WITH sector_counts AS (
    SELECT
        event_id,
        jsonb_object_keys(transmission_vector) as sector
    FROM event_transmission
)
SELECT
    event_id,
    COUNT(DISTINCT sector) as sector_count
FROM sector_counts
GROUP BY event_id
HAVING COUNT(DISTINCT sector) != 11;
-- Expected: Empty result (all should have 11 sectors)

-- ─────────────────────────────────────────────────────────────────────────
-- SECTION 4: JSONB Query Performance Tests
-- ─────────────────────────────────────────────────────────────────────────

-- Query 4: Find all events where Energy (XLE) benefits > 0.8
SELECT
    date,
    event_type,
    confidence,
    (transmission_vector->>'XLE')::float as xle_strength
FROM event_transmission
WHERE (transmission_vector->>'XLE')::float > 0.8
ORDER BY date DESC;
-- Expected: 2026-03-20 (supply_shock_oil, XLE=1.0)
--           2026-02-20 (war_geopolitical, XLE=0.8)

-- Query 5: Find all events where Tech (XLK) hurt < -0.5
SELECT
    date,
    event_type,
    (transmission_vector->>'XLK')::float as xlk_strength
FROM event_transmission
WHERE (transmission_vector->>'XLK')::float < -0.5
ORDER BY (transmission_vector->>'XLK')::float ASC;
-- Expected: 2026-03-20 (XLK=-0.95)
--           2026-03-15 (XLK=-0.8)
--           2026-03-10 (XLK=-0.7)

-- Query 6: Find defensive rotation events (XLV, XLP, XLU all > 0.6)
SELECT
    date,
    event_type,
    (transmission_vector->>'XLV')::float as xlv,
    (transmission_vector->>'XLP')::float as xlp,
    (transmission_vector->>'XLU')::float as xlu
FROM event_transmission
WHERE (transmission_vector->>'XLV')::float > 0.6
  AND (transmission_vector->>'XLP')::float > 0.6
  AND (transmission_vector->>'XLU')::float > 0.6;
-- Expected: 2026-03-10 (risk_off_credit_stress)
--           2026-02-28 (recession_demand_collapse)

-- Query 7: Find events with extreme impacts (any sector > 0.9 or < -0.9)
WITH extreme_impacts AS (
    SELECT
        date,
        event_type,
        key as sector,
        value::text::float as strength
    FROM event_transmission,
    LATERAL jsonb_each(transmission_vector)
    WHERE value::text::float > 0.9 OR value::text::float < -0.9
)
SELECT
    date,
    event_type,
    sector,
    strength
FROM extreme_impacts
ORDER BY date DESC, strength DESC;

-- ─────────────────────────────────────────────────────────────────────────
-- SECTION 5: Statistical Analysis
-- ─────────────────────────────────────────────────────────────────────────

-- Query 8: Event type distribution
SELECT
    event_type,
    COUNT(*) as count,
    AVG(confidence) as avg_confidence,
    MIN(date) as earliest,
    MAX(date) as latest
FROM event_transmission
GROUP BY event_type
ORDER BY count DESC;

-- Query 9: Sector impact statistics (across all events)
WITH sector_stats AS (
    SELECT
        key as sector,
        value::text::float as strength
    FROM event_transmission,
    LATERAL jsonb_each(transmission_vector)
)
SELECT
    sector,
    COUNT(*) as events_count,
    ROUND(AVG(strength)::numeric, 3) as avg_strength,
    ROUND(MIN(strength)::numeric, 3) as min_strength,
    ROUND(MAX(strength)::numeric, 3) as max_strength,
    ROUND(STDDEV(strength)::numeric, 3) as stddev
FROM sector_stats
GROUP BY sector
ORDER BY avg_strength DESC;

-- Query 10: Winners vs Losers count per event
SELECT
    date,
    event_type,
    SUM(CASE WHEN value::text::float > 0.5 THEN 1 ELSE 0 END) as winners,
    SUM(CASE WHEN value::text::float < -0.5 THEN 1 ELSE 0 END) as losers,
    SUM(CASE WHEN value::text::float BETWEEN -0.5 AND 0.5 THEN 1 ELSE 0 END) as neutral
FROM event_transmission,
LATERAL jsonb_each(transmission_vector)
GROUP BY date, event_type
ORDER BY date DESC;

-- ─────────────────────────────────────────────────────────────────────────
-- SECTION 6: Integration with Existing Tables
-- ─────────────────────────────────────────────────────────────────────────

-- Query 11: Join with daily_decisions (check if decisions exist for these dates)
SELECT
    et.date,
    et.event_type,
    et.confidence as event_confidence,
    dd.status as decision_status,
    dd.final_weights->>'XLE' as xle_final_weight
FROM event_transmission et
LEFT JOIN daily_decisions dd ON et.date = dd.date
ORDER BY et.date DESC;

-- Query 12: Join with daily_news_digest (compare macro_regime with event_type)
SELECT
    et.date,
    et.event_type,
    et.confidence as event_conf,
    dnd.macro_regime,
    dnd.confidence as digest_conf
FROM event_transmission et
LEFT JOIN daily_news_digest dnd ON et.date = dnd.date
ORDER BY et.date DESC;

-- Query 13: Join with decision_log (compare AI decisions with transmission)
SELECT
    et.date,
    et.event_type,
    (et.transmission_vector->>'XLE')::float as xle_transmission,
    dl.ai_regime,
    dl.qc_regime,
    dl.regime_override
FROM event_transmission et
LEFT JOIN decision_log dl ON et.date = dl.date
ORDER BY et.date DESC;

-- ─────────────────────────────────────────────────────────────────────────
-- SECTION 7: Data Quality Checks
-- ─────────────────────────────────────────────────────────────────────────

-- Check 14: Ensure no duplicate event_ids
SELECT event_id, COUNT(*)
FROM event_transmission
GROUP BY event_id
HAVING COUNT(*) > 1;
-- Expected: Empty (no duplicates)

-- Check 15: Verify all strengths are in valid range [-1.0, 1.0]
WITH range_check AS (
    SELECT
        date,
        event_id,
        key as sector,
        value::text::float as strength
    FROM event_transmission,
    LATERAL jsonb_each(transmission_vector)
    WHERE value::text::float < -1.0 OR value::text::float > 1.0
)
SELECT * FROM range_check;
-- Expected: Empty (all values in valid range)

-- Check 16: Ensure all expected sectors are present
WITH expected_sectors AS (
    SELECT unnest(ARRAY['XLE', 'XLF', 'XLV', 'XLI', 'XLP', 'XLU', 'XLY', 'XLK', 'XLC', 'XLRE', 'XLB']) as sector
),
actual_sectors AS (
    SELECT DISTINCT
        event_id,
        jsonb_object_keys(transmission_vector) as sector
    FROM event_transmission
)
SELECT
    et.event_id,
    es.sector as missing_sector
FROM event_transmission et
CROSS JOIN expected_sectors es
LEFT JOIN actual_sectors a ON et.event_id = a.event_id AND es.sector = a.sector
WHERE a.sector IS NULL;
-- Expected: Empty (all sectors present in all events)

-- ─────────────────────────────────────────────────────────────────────────
-- SECTION 8: Performance Optimization (Optional)
-- ─────────────────────────────────────────────────────────────────────────

-- Create GIN index for JSONB queries (if data volume is large)
-- Uncomment below to create:
-- CREATE INDEX IF NOT EXISTS idx_transmission_vector
-- ON event_transmission
-- USING GIN (transmission_vector);

-- Check index existence
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'event_transmission';

-- ─────────────────────────────────────────────────────────────────────────
-- SECTION 9: Cleanup (Use with caution!)
-- ─────────────────────────────────────────────────────────────────────────

-- To delete all test data (CAUTION!)
-- Uncomment to execute:
-- DELETE FROM event_transmission;

-- To reset auto-increment ID
-- Uncomment to execute:
-- ALTER SEQUENCE event_transmission_id_seq RESTART WITH 1;

-- ─────────────────────────────────────────────────────────────────────────
-- SECTION 10: Sample Query for Step 2 Integration (Preview)
-- ─────────────────────────────────────────────────────────────────────────

-- This is how Step 2 will query transmission vectors in Week 2
SELECT
    transmission_vector
FROM event_transmission
WHERE date = '2026-03-20'
AND event_id = 'macro_2026-03-20';
-- Returns: Full JSONB transmission vector for use in Step 2 prompt

-- =========================================================================
-- END OF TEST QUERIES
-- =========================================================================

-- Summary: Run sections 1-7 for complete validation
-- Expected total time: ~30 seconds for all queries
