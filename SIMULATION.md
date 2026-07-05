# SIMULATION.md — How to Run Simulations

Three simulation modes. All run against the ticks table and output comparative PnL.

## 1. Exit Strategy Simulator

Replays exit decisions against historical ticks with modified parameters.

**Parameters you can tune:**
- `phase0_ms`: phase 0 duration (default 300,000 = 5min)
- `trail_tiers`: peak-adaptive trail percentages
- `smart_threshold`: minimum smart wallet count for HOLD
- `vol_health_threshold`: min 5m vol for "healthy" status
- `stall_timeout_ms`: zero-buys death timeout

**How it works:**
For each position, read ticks in order. At each tick, apply the exit state machine with the new parameters. Determine if exit would happen at a different tick than it actually did. Compute resulting PnL.

**Script:** `scripts/simulate_exit.py` (usage below)

```bash
python3 scripts/simulate_exit.py \
  --db data/camus-warehouse.db \
  --phase0-ms 240000 \
  --trail-tiers "250:10,100:16,40:22,15:30,0:40" \
  --smart-threshold 5 \
  --vol-health 2000
```

**Output:** For each position, shows original vs simulated exit, PnL delta, and aggregate summary.

## 2. Entry Filter Simulator

Re-runs filters against historical screening data.

**Parameters:**
- `mcap_floor`: minimum entry mcap
- `rugpull_threshold`: rugpull filter cutoff
- `stale_gate_hours`: max token age for re-trending

```bash
python3 scripts/simulate_entry.py \
  --db data/camus-warehouse.db \
  --mcap-floor 20000 \
  --rugpull-threshold 20000
```

## 3. Walk-Forward Grid Search

Hyperparameter search across time windows. Tests every parameter combination and validates on out-of-sample windows.

```bash
python3 scripts/grid_search.py \
  --db data/camus-warehouse.db \
  --window-days 7 \
  --parameters trail_tiers,smart_threshold,phase0_ms
```

## Understanding Results

Each simulation outputs:
- **Total PnL lift**: simulated_sum - original_sum
- **WR change**: simulated_wr - original_wr
- **Capture ratio delta**: simulated_capture - original_capture
- **False positive rate**: extra losses caused by parameter change
- **Per-position breakdown**: which positions benefited vs were hurt

## Important Caveats

1. **Simulations are not predictions.** Past performance ≠ future results. Market regimes shift.
2. **Slippage gap.** The sim assumes fills at tick prices. Real executions have slippage (add `--slippage-pct 0.5` to conservative estimate).
3. **Regime bias.** The 14-day window might overfit to current regime. Walk-forward mitigates this.
4. **No order-book effects.** The sim doesn't model how your exit order impacts the mcap it fills at.
