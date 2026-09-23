-- 04_match_erp_dwh.sql
-- Check that every ERP order reaches the data warehouse exactly once,
-- in the right month and with the right amount.

DROP TABLE IF EXISTS dwh_by_order;
CREATE TABLE dwh_by_order AS
SELECT
    source_order_id                 AS order_id,
    count(*)                        AS n_rows,
    round(sum(amount_eur), 2)       AS dwh_amount_eur,
    min(booking_month)              AS booking_month
FROM dwh_bookings
GROUP BY source_order_id;

DROP TABLE IF EXISTS recon_erp_dwh;
CREATE TABLE recon_erp_dwh AS
SELECT
    e.order_id,
    CASE
        WHEN d.order_id IS NULL                             THEN 'MISSING_IN_DWH'
        WHEN d.n_rows > 1                                   THEN 'DWH_DUPLICATE'
        WHEN abs(d.dwh_amount_eur - e.amount_eur) > 0.01    THEN 'DWH_AMOUNT_MISMATCH'
        WHEN d.booking_month <> e.order_month               THEN 'DWH_PERIOD_MISMATCH'
        ELSE 'MATCHED'
    END                                                     AS status,
    e.order_month,
    e.amount_eur                                            AS erp_amount_eur,
    d.dwh_amount_eur,
    round(coalesce(d.dwh_amount_eur, 0) - e.amount_eur, 2)  AS diff_eur,
    coalesce(d.n_rows, 0)                                   AS dwh_rows
FROM stg_erp e
LEFT JOIN dwh_by_order d ON d.order_id = e.order_id

UNION ALL

-- Rows in the DWH that point to an order ERP does not know
SELECT
    d.order_id, 'DWH_ORPHAN', d.booking_month,
    NULL, d.dwh_amount_eur, d.dwh_amount_eur, d.n_rows
FROM dwh_by_order d
WHERE d.order_id NOT IN (SELECT order_id FROM stg_erp);
