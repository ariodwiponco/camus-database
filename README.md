# Camus Dataset

Curated trading history from **Camus** — a Solana memecoin trenching bot.

## Contents

| File | Size | Description |
|------|------|-------------|
| `data/camus-warehouse.db` | 22.9 MB | Clean 7-table warehouse (this repo) |
| `data/camus-full-db.zst` | ~700 MB (not included) | Full 47-table operational DB — contact Ario |
| `scripts/analyze.py` | — | Quick analysis script |
| `sample_queries.sql` | — | Ready-to-run SQL |

## Schema (7 tables, 251K rows)

```
positions   → 3,792 trades, 80+ features each
ticks       → 62,543 snapshots during positions
post_mortem → 2,502 post-exit peak tracks
screening   → 17,510 filter rejection records
simulations → 8,312 what-if experiments (5 types)
enrichment  → 4,618 external data rows
learning    → 12,791 lessons + formal hypotheses
```

## Quick Analysis

```bash
pip install -r requirements.txt  # or just use sqlite3 directly
python3 scripts/analyze.py
```

Or raw SQL:
```bash
sqlite3 data/camus-warehouse.db "
  SELECT exit_reason, COUNT(*) n, ROUND(AVG(pnl_sol),4) avg_pnl
  FROM positions GROUP BY exit_reason ORDER BY avg_pnl;
"
```

## Read This First

- [AGENTS.md](AGENTS.md) — guide for AI agents
- [SCHEMA.md](SCHEMA.md) — full data dictionary
- [GLOSSARY.md](GLOSSARY.md) — domain terms
- [QUERIES.md](QUERIES.md) — 20+ ready SQL queries
- [SIMULATION.md](SIMULATION.md) — simulation guide
- [DOWNLOAD.md](DOWNLOAD.md) — full DB download info

## License

Contact Ario for usage terms.
