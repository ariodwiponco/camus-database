# Download Full Dataset

The `camus-warehouse.db` (22.9 MB, 7 tables, 251K rows) is included in this repo at `data/camus-warehouse.db`.

## Full Operational Database

**47 tables, 2.6 GB raw (427 MB encrypted).** Includes all raw ticks, candidates, signal events, and post-exit samples.

### Download

```bash
# 1. Download encrypted file
wget https://github.com/ariodwiponco/camus-database/releases/download/v1.0-full/camus-full-db.enc

# 2. Decrypt (you'll be prompted for the password)
openssl enc -aes-256-cbc -d -pbkdf2 -in camus-full-db.enc -out camus-full-db.zst

# 3. Decompress
zstd -d camus-full-db.zst

# Result: camus-full-db (rename to camus.sqlite)
mv camus-full-db camus.sqlite
```

### Password

**Ask Ario for the password.** Not included in this repo.

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
