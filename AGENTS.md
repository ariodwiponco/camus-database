# AGENTS.md — Camus Dataset Guide for AI Agents

## Identity

This repo contains **Camus**, a Solana memecoin trenching bot's complete trading history. The dataset is structured for AI agents (and their human operators) to learn entry/exit strategy design from real data.

## Query Pattern

Primary interface: **sqlite3** on the warehouse DB. Start here:

```sql
-- Win rate by exit reason
SELECT exit_reason, COUNT(*) n, ROUND(AVG(pnl_sol),4) avg_pnl,
  ROUND(SUM(CASE WHEN pnl_sol>0 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) wr,
  ROUND(AVG(hold_ms/60000.0),1) hold_min
FROM positions GROUP BY exit_reason ORDER BY wr;

-- Three-bucket distribution
SELECT CASE WHEN pnl_sol > 0 THEN 'yielded'
       WHEN pnl_sol < -0.01 THEN 'dead_entries'
       ELSE 'middle' END as bucket,
  COUNT(*) n, ROUND(SUM(pnl_sol),2) total_pnl, ROUND(AVG(pnl_sol),4) avg_pnl
FROM positions GROUP BY bucket ORDER BY avg_pnl;
```

## Domain Language

The dataset uses these concepts. **Keep them as trigger words** for quick recall:

### Three-Bucket System
- **yielded**: positions where `pnl_sol > 0` — the winners
- **dead_entries**: positions where `pnl_sol < -0.01` — losses (anything worse than 1% fee bleed)
- **middle**: everything between — breakeven / small bleed

### Position Archetypes
- `banger`: token that 2x'd from entry — captured by `f_obs_missed_mult >= 1.0`
- `rug`: token that dropped 70%+ from entry — SL triggered
- `flat`: token that never moved >20%
- `runner`: token that 300%+ peaked — trail should capture these

### Exit Reason Priority
1. SL — -70% hard floor (12.9% WR — kills us)
2. EXIT_EMERGENCY — vol crash + distribution (signal-driven)
3. VOL_DISTRIBUTION — flow ratio collapse (separated Jul 2)
4. STALE — phased exit on dead air
5. TRAILING_TP — peak-adaptive trail triggered (39.3% WR — main exit)
6. TP — take profit hit
7. LIQUIDITY_CRASH — liquidity dropped below threshold

### Key Metrics
- `capture_ratio`: pnl_sol / reachable_sol. How much of potential profit we keep (target: >30%)
- `missed_multiple`: peak_captured / entry_mcap — how many x we caught
- `ath_missed_multiple` (in screening): how many x a rejected token went on to do
- `flow_ratio`: buy_vol_5m / sell_vol_5m. <0.8 = distribution (selling pressure)

## Shadow Tables (Pre-computed What-Ifs)

The `simulations` table has 5 types. Each tells you what WOULD have happened under a different strategy:

1. **entry_shadow**: would a new filter rule have blocked a winner?
2. **moonbag**: what if we left 25% of position to keep running?
3. **runner_mode**: what if we held with scale-out tiers (sell 50% at +150%, 25% at +400%)?
4. **conviction**: what if we entered at first signal (earlier, lower mcap)?
5. **reentry**: what if we bought again after exit (at a lower mcap)?

Don't re-run these. They're already computed from real ticks.

## Reading the Cleaning Script

`scripts/analyze.py` shows the standard analysis workflow. Use it as a template for your own queries.

## Data Integrity

- Positions with `execution_mode = 'dry_run'` are paper trades (same logic, no real SOL risk)
- Positions with `exit_reason` containing `VOIDED` are bug-fix artifacts — exclude from analysis
- The warehouse is a **read-only snapshot**. It won't be updated live.
