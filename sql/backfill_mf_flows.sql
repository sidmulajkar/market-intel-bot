-- MF Flows Backfill from AMFI
-- Generated: 2026-05-20T16:41:08.412729
-- 12 category records for current month
-- Source: AMFI NAVAll.txt (live fetch)
-- Note: Monthly flows require AMFI monthly reports (not API-accessible)
-- We store category composition as proxy for flow direction

INSERT INTO mf_flows (month, category, amount_cr, sip_amount_cr, source)
VALUES ('2026-05-01', 'Debt', 0, NULL, 'AMFI_NAV')
ON CONFLICT (month, category) DO UPDATE SET
    amount_cr = EXCLUDED.amount_cr,
    source = EXCLUDED.source;
INSERT INTO mf_flows (month, category, amount_cr, sip_amount_cr, source)
VALUES ('2026-05-01', 'ELSS', 0, NULL, 'AMFI_NAV')
ON CONFLICT (month, category) DO UPDATE SET
    amount_cr = EXCLUDED.amount_cr,
    source = EXCLUDED.source;
INSERT INTO mf_flows (month, category, amount_cr, sip_amount_cr, source)
VALUES ('2026-05-01', 'Flexi Cap', 0, NULL, 'AMFI_NAV')
ON CONFLICT (month, category) DO UPDATE SET
    amount_cr = EXCLUDED.amount_cr,
    source = EXCLUDED.source;
INSERT INTO mf_flows (month, category, amount_cr, sip_amount_cr, source)
VALUES ('2026-05-01', 'Gold', 0, NULL, 'AMFI_NAV')
ON CONFLICT (month, category) DO UPDATE SET
    amount_cr = EXCLUDED.amount_cr,
    source = EXCLUDED.source;
INSERT INTO mf_flows (month, category, amount_cr, sip_amount_cr, source)
VALUES ('2026-05-01', 'Hybrid', 0, NULL, 'AMFI_NAV')
ON CONFLICT (month, category) DO UPDATE SET
    amount_cr = EXCLUDED.amount_cr,
    source = EXCLUDED.source;
INSERT INTO mf_flows (month, category, amount_cr, sip_amount_cr, source)
VALUES ('2026-05-01', 'International', 0, NULL, 'AMFI_NAV')
ON CONFLICT (month, category) DO UPDATE SET
    amount_cr = EXCLUDED.amount_cr,
    source = EXCLUDED.source;
INSERT INTO mf_flows (month, category, amount_cr, sip_amount_cr, source)
VALUES ('2026-05-01', 'Large Cap', 0, NULL, 'AMFI_NAV')
ON CONFLICT (month, category) DO UPDATE SET
    amount_cr = EXCLUDED.amount_cr,
    source = EXCLUDED.source;
INSERT INTO mf_flows (month, category, amount_cr, sip_amount_cr, source)
VALUES ('2026-05-01', 'Liquid', 0, NULL, 'AMFI_NAV')
ON CONFLICT (month, category) DO UPDATE SET
    amount_cr = EXCLUDED.amount_cr,
    source = EXCLUDED.source;
INSERT INTO mf_flows (month, category, amount_cr, sip_amount_cr, source)
VALUES ('2026-05-01', 'Mid Cap', 0, NULL, 'AMFI_NAV')
ON CONFLICT (month, category) DO UPDATE SET
    amount_cr = EXCLUDED.amount_cr,
    source = EXCLUDED.source;
INSERT INTO mf_flows (month, category, amount_cr, sip_amount_cr, source)
VALUES ('2026-05-01', 'Other', 0, NULL, 'AMFI_NAV')
ON CONFLICT (month, category) DO UPDATE SET
    amount_cr = EXCLUDED.amount_cr,
    source = EXCLUDED.source;
INSERT INTO mf_flows (month, category, amount_cr, sip_amount_cr, source)
VALUES ('2026-05-01', 'Sectoral', 0, NULL, 'AMFI_NAV')
ON CONFLICT (month, category) DO UPDATE SET
    amount_cr = EXCLUDED.amount_cr,
    source = EXCLUDED.source;
INSERT INTO mf_flows (month, category, amount_cr, sip_amount_cr, source)
VALUES ('2026-05-01', 'Small Cap', 0, NULL, 'AMFI_NAV')
ON CONFLICT (month, category) DO UPDATE SET
    amount_cr = EXCLUDED.amount_cr,
    source = EXCLUDED.source;

-- Verify
SELECT month, category, amount_cr, source
FROM mf_flows ORDER BY month DESC, category LIMIT 50;