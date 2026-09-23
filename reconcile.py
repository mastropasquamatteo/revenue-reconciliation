"""
Run the reconciliation and check it against the injected issues.

Steps:
  1. load the CSV files from data/ into a SQLite database
  2. run the SQL scripts in sql/ in order
  3. export the results to output/
  4. compare what was detected with what was injected

Run:  python reconcile.py
"""

from pathlib import Path
import sqlite3

import pandas as pd

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
SQL_DIR = ROOT / "sql"
OUT_DIR = ROOT / "output"

SOURCES = ["crm_opportunities", "erp_orders", "dwh_bookings", "fx_rates"]

# Which status each injected issue should produce, and in which check.
EXPECTED = {
    "missing_order":      ("recon_crm_erp", "opp_id",   "MISSING_IN_ERP"),
    "amount_mismatch":    ("recon_crm_erp", "opp_id",   "AMOUNT_MISMATCH"),
    "period_shift":       ("recon_crm_erp", "opp_id",   "PERIOD_MISMATCH"),
    "ref_format":         ("recon_crm_erp", "opp_id",   "REFERENCE_NORMALISED"),
    "ref_missing":        ("recon_crm_erp", "opp_id",   "SUGGESTED_MATCH"),
    "currency_invoiced":  ("recon_crm_erp", "opp_id",   "FX_EXPLAINED"),
    "split_order":        ("recon_crm_erp", "opp_id",   "SPLIT_ORDER"),
    "no_crm_opportunity": ("recon_crm_erp", "order_id", "NO_CRM_OPPORTUNITY"),
    "dwh_duplicate":      ("recon_erp_dwh", "order_id", "DWH_DUPLICATE"),
    "dwh_missing":        ("recon_erp_dwh", "order_id", "MISSING_IN_DWH"),
}


def load_sources(con: sqlite3.Connection) -> None:
    for name in SOURCES:
        df = pd.read_csv(DATA_DIR / f"{name}.csv", dtype=str, keep_default_na=False)
        for col in ("amount", "net_amount", "amount_eur", "rate_to_eur"):
            if col in df.columns:
                df[col] = df[col].astype(float)
        df.to_sql(name, con, index=False, if_exists="replace")


def run_sql(con: sqlite3.Connection) -> None:
    for script in sorted(SQL_DIR.glob("*.sql")):
        con.executescript(script.read_text(encoding="utf-8"))


def evaluate(con: sqlite3.Connection) -> pd.DataFrame:
    """Per issue type: how many were injected, found, missed, or flagged wrongly."""
    injected = pd.read_csv(DATA_DIR / "injected_issues.csv", dtype=str)
    rows = []
    for issue, (table, key, status) in EXPECTED.items():
        expected_ids = set(injected.loc[injected["issue_type"] == issue, key].dropna())
        detected_ids = set(
            pd.read_sql(f"SELECT {key} FROM {table} WHERE status = ?", con, params=(status,))[key]
            .dropna()
        )
        rows.append(
            {
                "injected_issue": issue,
                "expected_status": status,
                "injected": len(expected_ids),
                "detected": len(expected_ids & detected_ids),
                "missed": len(expected_ids - detected_ids),
                "false_alarms": len(detected_ids - expected_ids),
            }
        )
    return pd.DataFrame(rows)


def to_markdown(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join(f"{v:,.2f}" if isinstance(v, float) else str(v) for v in row) + " |")
    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    db_path = OUT_DIR / "reconciliation.db"
    db_path.unlink(missing_ok=True)

    with sqlite3.connect(db_path) as con:
        load_sources(con)
        run_sql(con)

        crm_erp = pd.read_sql("SELECT * FROM recon_crm_erp ORDER BY status, opp_id, order_id", con)
        erp_dwh = pd.read_sql("SELECT * FROM recon_erp_dwh ORDER BY status, order_id", con)
        summary = pd.read_sql("SELECT * FROM recon_summary ORDER BY check_name, n_records DESC", con)
        evaluation = evaluate(con)

    crm_erp.to_csv(OUT_DIR / "recon_crm_erp.csv", index=False)
    erp_dwh.to_csv(OUT_DIR / "recon_erp_dwh.csv", index=False)

    report = [
        "# Reconciliation summary",
        "",
        "## Status by check",
        "",
        to_markdown(summary),
        "",
        "## Detection check against injected issues",
        "",
        to_markdown(evaluation),
        "",
    ]
    (OUT_DIR / "summary.md").write_text("\n".join(report), encoding="utf-8")

    print(summary.to_string(index=False))
    print()
    print(evaluation.to_string(index=False))

    total_missed = int(evaluation["missed"].sum())
    total_false = int(evaluation["false_alarms"].sum())
    print(f"\nMissed: {total_missed}   False alarms: {total_false}")


if __name__ == "__main__":
    main()
