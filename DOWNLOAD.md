# Download Full Dataset

The `camus-warehouse.db` (22.9 MB, 7 tables, 251K rows) is included in this repo at `data/camus-warehouse.db`.

## Full Operational Database

**47 tables, 2.6 GB raw (427 MB zstd compressed).** Includes all raw ticks, candidates, signal events, and post-exit samples.

### Download

```bash
# 1. Download all parts from GitHub Release
wget https://github.com/ariodwiponco/camus-database/releases/download/v1.0-full/full-db.zst.partaa
wget https://github.com/ariodwiponco/camus-database/releases/download/v1.0-full/full-db.zst.partab
wget https://github.com/ariodwiponco/camus-database/releases/download/v1.0-full/full-db.zst.partac
wget https://github.com/ariodwiponco/camus-database/releases/download/v1.0-full/full-db.zst.partad
wget https://github.com/ariodwiponco/camus-database/releases/download/v1.0-full/full-db.zst.partae
wget https://github.com/ariodwiponco/camus-database/releases/download/v1.0-full/full-db.zst.partaf
wget https://github.com/ariodwiponco/camus-database/releases/download/v1.0-full/full-db.zst.partag
wget https://github.com/ariodwiponco/camus-database/releases/download/v1.0-full/full-db.zst.partah
wget https://github.com/ariodwiponco/camus-database/releases/download/v1.0-full/full-db.zst.partai

# 2. Join parts
cat full-db.zst.part* > camus-full-db.zst

# 3. Decompress (zstd)
zstd -d camus-full-db.zst

# Result: camus.sqlite (2.6 GB)
```

Or one-liner:
```bash
for p in a b c d e f g h i; do wget "https://github.com/ariodwiponco/camus-database/releases/download/v1.0-full/full-db.zst.part${p}a${p}"; done && cat full-db.zst.part* > camus-full-db.zst && zstd -d camus-full-db.zst
```

### What's extra in the full DB vs the warehouse

| Table | Rows | Content |
|-------|------|---------|
| `signal_events` | 95,512 | Every inbound signal (Telegram, GMGN) |
| `candidates` | 27,441 | Full screening pipeline with filter results + JSON |
| `decision_logs` | 7,068 | Full decision batches with guardrails |
| `llm_decisions` | 8,177 | LLM verdicts (full response JSON) |
| `dry_run_trades` | 8,507 | Individual buy/sell legs |
| `post_exit_samples` | 245,234 | Raw mcap samples after each exit |
| `trajectory_samples` | 147,307 | Raw samples across full lifespan |
| `position_ticks` | 62,517 | Per-position tick snapshots |
| + 12 more tables | — | ATH caches, enrichments, logs |
