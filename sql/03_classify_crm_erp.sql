-- 03_classify_crm_erp.sql
-- One row per opportunity (or per unmatched order), with a single status.
-- ERP orders are summed per opportunity first: a deal invoiced in
-- two orders is one deal, not two amount mismatches.
-- Order of the CASE matters: a real difference in money wins over
-- a timing difference, which wins over differences that are only cosmetic.

DROP TABLE IF EXISTS erp_by_opp;
CREATE TABLE erp_by_opp AS
SELECT
    p.opp_id,
    group_concat(e.order_id, ';')               AS order_ids,
    count(*)                                    AS n_orders,
    max(p.match_method = 'SUGGESTED')           AS is_suggested,
    round(sum(e.amount_eur), 2)                 AS erp_amount_eur,
    min(e.order_month)                          AS first_order_month,
    max(e.order_month)                          AS last_order_month,
    count(DISTINCT e.currency)                  AS n_currencies,
    min(e.currency)                             AS erp_currency,
    max(e.opp_ref_raw <> p.opp_id)              AS ref_was_normalised
FROM crm_erp_pairs p
JOIN stg_erp e ON e.order_id = p.order_id
GROUP BY p.opp_id;

DROP TABLE IF EXISTS recon_crm_erp;
CREATE TABLE recon_crm_erp AS

-- Opportunities with at least one order
SELECT
    c.opp_id,
    b.order_ids                                 AS order_id,
    CASE
        WHEN b.is_suggested = 1                                          THEN 'SUGGESTED_MATCH'
        WHEN abs(b.erp_amount_eur - c.amount_eur) > 0.005 * c.amount_eur THEN 'AMOUNT_MISMATCH'
        WHEN b.n_orders > 1                                              THEN 'SPLIT_ORDER'
        WHEN b.first_order_month <> c.close_month
          OR b.last_order_month  <> c.close_month                        THEN 'PERIOD_MISMATCH'
        WHEN b.n_currencies > 1 OR b.erp_currency <> c.currency          THEN 'FX_EXPLAINED'
        WHEN b.ref_was_normalised = 1                                    THEN 'REFERENCE_NORMALISED'
        ELSE 'MATCHED'
    END                                         AS status,
    c.account_id,
    c.close_month,
    b.first_order_month                         AS order_month,
    c.amount_eur                                AS crm_amount_eur,
    b.erp_amount_eur,
    round(b.erp_amount_eur - c.amount_eur, 2)   AS diff_eur
FROM erp_by_opp b
JOIN stg_crm c ON c.opp_id = b.opp_id

UNION ALL

-- Won in CRM, nothing in ERP
SELECT
    c.opp_id, NULL, 'MISSING_IN_ERP',
    c.account_id, c.close_month, NULL,
    c.amount_eur, NULL, round(-c.amount_eur, 2)
FROM stg_crm c
WHERE c.stage = 'Closed Won'
  AND c.opp_id NOT IN (SELECT opp_id FROM crm_erp_pairs)

UNION ALL

-- Invoiced in ERP, no opportunity behind it
SELECT
    NULL, e.order_id, 'NO_CRM_OPPORTUNITY',
    e.customer_code, NULL, e.order_month,
    NULL, e.amount_eur, e.amount_eur
FROM stg_erp e
WHERE e.order_id NOT IN (SELECT order_id FROM crm_erp_pairs);
