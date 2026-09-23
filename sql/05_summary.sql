-- 05_summary.sql
-- Count and money impact per status, both reconciliations together.

DROP VIEW IF EXISTS recon_summary;
CREATE VIEW recon_summary AS
SELECT 'CRM vs ERP' AS check_name, status,
       count(*) AS n_records,
       round(sum(abs(coalesce(diff_eur, 0))), 2) AS abs_diff_eur
FROM recon_crm_erp
GROUP BY status
UNION ALL
SELECT 'ERP vs DWH', status,
       count(*),
       round(sum(abs(coalesce(diff_eur, 0))), 2)
FROM recon_erp_dwh
GROUP BY status;
