#!/usr/bin/env python3
"""Camus Dataset Analysis — quick stats from the clean warehouse."""
import sqlite3, sys, os
from pathlib import Path

DB = Path(__file__).parent.parent / "data" / "camus-warehouse.db"

def query(sql, db=None):
    con = sqlite3.connect(str(db or DB))
    cur = con.execute(sql)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    con.close()
    return cols, rows

def print_table(cols, rows, fmt="pretty"):
    if not rows:
        print("(no rows)")
        return
    # column widths
    widths = [len(c) for c in cols]
    for r in rows:
        for i, v in enumerate(r):
            widths[i] = max(widths[i], len(str(v)))
    # header
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    print(sep)
    print("| " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(cols)) + " |")
    print(sep)
    for r in rows:
        print("| " + " | ".join(str(v).ljust(widths[i]) for i, v in enumerate(r)) + " |")
    print(sep)

def main():
    if not DB.exists():
        print(f"❌ DB not found: {DB}")
        print("Run from repo root or specify --db <path>")
        sys.exit(1)

    print(f"📊 Camus Warehouse Analysis")
    print(f"   DB: {DB} ({DB.stat().st_size / 1048576:.1f} MB)\n")

    # 1. Overview
    cols, rows = query("""
        SELECT 'positions' t, COUNT(*) r FROM positions
        UNION ALL SELECT 'ticks', COUNT(*) FROM ticks
        UNION ALL SELECT 'post_mortem', COUNT(*) FROM post_mortem
        UNION ALL SELECT 'screening', COUNT(*) FROM screening
        UNION ALL SELECT 'simulations', COUNT(*) FROM simulations
        UNION ALL SELECT 'enrichment', COUNT(*) FROM enrichment
        UNION ALL SELECT 'learning', COUNT(*) FROM learning
        ORDER BY r DESC;
    """)
    print("=== Table Sizes ===")
    print_table(cols, rows)

    # 2. Three-bucket
    cols, rows = query("""
        SELECT CASE WHEN pnl_sol > 0 THEN 'yielded'
               WHEN pnl_sol < -0.01 THEN 'dead_entries'
               ELSE 'middle' END bucket,
          COUNT(*) n,
          ROUND(SUM(pnl_sol),2) total_pnl,
          ROUND(AVG(pnl_sol),4) avg_pnl,
          ROUND(SUM(CASE WHEN pnl_sol>0 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) wr,
          ROUND(AVG(hold_ms/60000.0),1) hold_min
        FROM positions GROUP BY bucket ORDER BY avg_pnl;
    """)
    print("\n=== Three-Bucket ===")
    print_table(cols, rows)

    # 3. Exit reasons
    cols, rows = query("""
        SELECT exit_reason, COUNT(*) n,
          ROUND(AVG(pnl_sol),4) avg_pnl,
          ROUND(SUM(pnl_sol),2) total_pnl,
          ROUND(SUM(CASE WHEN pnl_sol>0 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) wr,
          ROUND(AVG(peak_pct),1) avg_peak,
          ROUND(AVG(hold_ms/60000.0),1) hold_min
        FROM positions
        WHERE exit_reason NOT LIKE 'VOIDED%'
        GROUP BY exit_reason ORDER BY total_pnl;
    """)
    print("\n=== Exit Reasons ===")
    print_table(cols, rows)

    # 4. MCAP bucket
    cols, rows = query("""
        SELECT CASE
          WHEN entry_mcap < 20000 THEN '<$20K'
          WHEN entry_mcap < 50000 THEN '$20-50K'
          WHEN entry_mcap < 100000 THEN '$50-100K'
          WHEN entry_mcap < 200000 THEN '$100-200K'
          ELSE '$200K+' END mcap,
          COUNT(*) n,
          ROUND(AVG(pnl_sol),4) avg_pnl,
          ROUND(SUM(CASE WHEN pnl_sol>0 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) wr,
          ROUND(AVG(peak_pct),1) avg_peak
        FROM positions GROUP BY mcap ORDER BY avg_pnl;
    """)
    print("\n=== Entry MCAP Buckets ===")
    print_table(cols, rows)

    # 5. Capture ratio
    cols, rows = query("""
        SELECT CASE
          WHEN peak_pct < 50 THEN 'flat (<50%)'
          WHEN peak_pct < 100 THEN 'mid (50-100%)'
          WHEN peak_pct < 150 THEN 'hot (100-150%)'
          ELSE 'runner (150%+)' END bucket,
          COUNT(*) n,
          ROUND(AVG(capture_ratio),2) avg_capture,
          ROUND(AVG(missed_multiple),2) missed_x,
          ROUND(AVG(peak_pct),1) avg_peak,
          ROUND(AVG(pnl_sol),4) avg_pnl
        FROM positions
        WHERE capture_ratio IS NOT NULL
        GROUP BY bucket ORDER BY min(peak_pct);
    """)
    print("\n=== Capture Ratio by Peak Tier ===")
    print_table(cols, rows)

    # 6. Screening regret
    cols, rows = query("""
        SELECT
          COUNT(*) total,
          ROUND(AVG(true_ath_mcap / NULLIF(entry_mcap_usd,0)),2) avg_missed_x,
          ROUND(SUM(CASE WHEN true_ath_mcap / NULLIF(entry_mcap_usd,0) >= 2 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) pct_2x_plus,
          ROUND(SUM(CASE WHEN resolution='pumped' THEN 1 ELSE 0 END)*100.0/COUNT(*),1) pct_pumped
        FROM screening;
    """)
    print("\n=== Screening Filter Regret ===")
    print_table(cols, rows)

    # 7. Simulations summary
    cols, rows = query("""
        SELECT sim_type, COUNT(*) n FROM simulations GROUP BY sim_type ORDER BY n DESC;
    """)
    print("\n=== Sim Types ===")
    print_table(cols, rows)

    # 8. Top 5 missed opportunities
    cols, rows = query("""
        SELECT p.symbol,
          ROUND(p.entry_mcap) entry, ROUND(p.exit_mcap) exit,
          ROUND(pm.post_peak_mult,1) missed_x,
          ROUND(p.pnl_sol,3) pnl,
          p.exit_reason
        FROM positions p
        JOIN post_mortem pm ON pm.position_id = p.id
        WHERE pm.post_peak_mult > 3 AND p.pnl_sol < 0
        ORDER BY pm.post_peak_mult DESC LIMIT 5;
    """)
    print("\n=== Top 5 Missed Opportunities (post-exit pump >3x) ===")
    print_table(cols, rows)

    # 9. Key learning
    cols, rows = query("""
        SELECT body, metric, n_size, verdict FROM learning
        WHERE type='hypothesis' AND status='confirmed'
        ORDER BY n_size DESC LIMIT 5;
    """)
    print("\n=== Top 5 Confirmed Hypotheses ===")
    print_table(cols, rows)

    print("\n✅ Done.")

if __name__ == "__main__":
    main()
