# SCHEMA.md — Full Data Dictionary

## positions (3,792 rows)

The core table. Every position Camus ever opened, with entry features, exit details, and outcome.

### Identity & Timing
| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Position ID (matches source) |
| `mint` | TEXT | Token mint address |
| `symbol` | TEXT | Token ticker symbol |
| `strategy_id` | TEXT | Strategy used ('sniper' default) |
| `route` | TEXT | Entry signal route (e.g. viktor_charge) |
| `opened_at` | TEXT | ISO timestamp of entry |
| `closed_at` | TEXT | ISO timestamp of exit |
| `hold_ms` | INTEGER | Duration from open to close in ms |

### Sizing & PnL
| Column | Type | Description |
|--------|------|-------------|
| `size_sol` | REAL | Position size in SOL |
| `calibrated_size_sol` | REAL | Calibrated size after slippage |
| `slippage_pct` | REAL | Slippage percentage of entry |
| `slippage_cost_sol` | REAL | SOL cost of slippage |
| `gross_pnl_sol` | REAL | Gross PnL before fees |
| `gross_pnl_percent` | REAL | Gross return % |
| `net_pnl_sol` | REAL | Net PnL after fees |
| `pnl_sol` | REAL | Final PnL in SOL (primary metric) |
| `pnl_percent` | REAL | Final return % |

### Entry / Exit Prices
| Column | Type | Description |
|--------|------|-------------|
| `entry_mcap` | REAL | Market cap at entry (USD) |
| `entry_price` | REAL | Token price at entry |
| `exit_mcap` | REAL | Market cap at exit |
| `exit_price` | REAL | Token price at exit |
| `high_water_mcap` | REAL | Highest mcap during hold |
| `low_water_mcap` | REAL | Lowest mcap during hold |

### Exit Details
| Column | Type | Description |
|--------|------|-------------|
| `exit_reason` | TEXT | Why we exited (SL, TRAILING_TP, etc.) |
| `exit_signal_state` | TEXT | Signal state at exit (NORMAL/EXIT/EXIT_EMERGENCY/HOLD) |
| `exit_signal_debounced` | TEXT | Debounced signal state |
| `dynamic_trail_pct` | REAL | Trail percentage that fired |
| `flow_ratio` | REAL | buy_vol/sell_vol ratio at exit |
| `smart_money` | INTEGER | Smart wallet count at exit |
| `smart_trend` | TEXT | Smart money direction (up/down/flat) |
| `tokenscan_composite` | INTEGER | TokenScan composite score |
| `exit_tag` | TEXT | Additional exit context label |

### Entry Features (f_* columns — from signal pipeline)
| Column | Type | Description |
|--------|------|-------------|
| `f_route` | TEXT | Signal route name |
| `f_hot_level` | REAL | GMGN hot level at entry (0-100) |
| `f_smart_count` | REAL | Smart wallet count at entry |
| `f_obs_missed_mult` | REAL | Key entry signal: observed missed multiple. **≥1.0 = banger gate** |
| `f_holder_count` | REAL | Holder count at entry |
| `f_fresh_rate` | REAL | Fresh wallet rate (0-1) |
| `f_gmgn_fees_sol` | REAL | GMGN total fees in SOL |
| `f_kol_count` | REAL | KOL wallet count |
| `f_audit_score` | REAL | Audit score |
| `f_moonbag_score` | REAL | Moonbag score |
| `f_tokenscan_score` | REAL | TokenScan score |
| `f_dev_status` | TEXT | Developer status (e.g. 'creator_close') |
| `f_dev_hold_rate` | REAL | Developer holding rate |
| `f_rugcheck_score` | REAL | RugCheck score |

### Entry Market State
| Column | Type | Description |
|--------|------|-------------|
| `liquidity_usd` | REAL | Liquidity in USD |
| `holder_count` | INTEGER | Number of holders |
| `gmgn_total_fees_sol` | REAL | GMGN total fees in SOL |
| `vol_mcap_ratio` | REAL | Volume-to-mcap ratio |
| `mcap_tier` | TEXT | MCAP bucket (micro/small/mid/large) |
| `gmgn_rug_ratio` | REAL | GMGN rug pull risk (0-1) |
| `gmgn_kol_count` | INTEGER | KOL count from GMGN |
| `gmgn_smart_count` | INTEGER | Smart wallet count from GMGN |
| `gmgn_insider_rate` | REAL | Insider wallet rate |
| `gmgn_bundler_rate` | REAL | Bundler rate |
| `gmgn_sniper_rate` | REAL | Sniper rate |
| `gmgn_burn_ratio` | REAL | LP burn ratio |
| `gmgn_renounced_mint` | INTEGER | Is mint renounced? (0/1) |
| `gmgn_is_honeypot` | INTEGER | Is honeypot? (0/1) |
| `gmgn_is_locked` | INTEGER | Is liquidity locked? (0/1) |

### Token Characteristics
| Column | Type | Description |
|--------|------|-------------|
| `is_graduated` | INTEGER | Token graduated from bonding curve |
| `token_age_at_entry_s` | INTEGER | Token age in seconds at entry |
| `regime_at_entry` | TEXT | Regime (trending/fee_claim/etc.) |

### Outcome Metrics
| Column | Type | Description |
|--------|------|-------------|
| `peak_pct` | REAL | Max % gain during hold |
| `max_drawdown_pct` | REAL | Max % drawdown |
| `time_to_peak_ms` | INTEGER | Milliseconds from entry to peak |
| `tick_count` | INTEGER | Number of position_ticks recorded |
| `exit_quality` | TEXT | Qualitative exit quality label |
| `regret_score` | REAL | How much we regret this exit (0-1) |
| `infirmary_recovered_pct` | REAL | Post-exit recovery % (if watched) |
| `infirmary_status` | TEXT | Recovery status |
| `capture_ratio` | REAL | pnl_sol / reachable_sol |
| `missed_multiple` | REAL | ATH_mult - 1 (how many x we missed) |
| `archetype` | TEXT | Position archetype label |

### Execution
| Column | Type | Description |
|--------|------|-------------|
| `execution_mode` | TEXT | 'dry_run' or 'live' |
| `entry_signature` | TEXT | Solana tx signature for entry |
| `exit_signature` | TEXT | Solana tx signature for exit |

---

## ticks (62,543 rows)

Per-position time-series. Every 10-15 seconds during a position's life.

| Column | Type | Description |
|--------|------|-------------|
| `position_id` | INTEGER | Foreign key → positions.id |
| `at_ms` | INTEGER | Timestamp in ms |
| `hold_ms` | INTEGER | Milliseconds since position opened |
| `mcap` | REAL | Current market cap USD |
| `price` | REAL | Current token price |
| `pnl_percent` | REAL | Unrealized PnL % |
| `peak_pct` | REAL | Highest PnL % achieved so far |
| `drawdown_pct` | REAL | Current drawdown from peak |
| `buys_5m` | INTEGER | Buy count in last 5 minutes |
| `sells_5m` | INTEGER | Sell count in last 5 minutes |
| `buy_vol_5m` | REAL | Buy volume in last 5 min |
| `sell_vol_5m` | REAL | Sell volume in last 5 min |
| `flow_ratio` | REAL | buy_vol_5m / sell_vol_5m |
| `smart_money` | INTEGER | Smart wallet count this tick |
| `hot_level` | REAL | GMGN hot level |
| `exit_signal_state` | TEXT | What the exit state machine decided |
| `trail_pct` | REAL | Current trail percentage |
| `holder_count` | INTEGER | Holder count |
| `kol_count` | INTEGER | KOL wallet count |
| `liquidity` | REAL | Liquidity USD |
| `sniper_wallets` | INTEGER | Sniper wallet count |
| `whale_wallets` | INTEGER | Whale wallet count |
| `dev_status` | TEXT | Developer status |
| `policy_signal` | TEXT | Policy signal label |

---

## post_mortem (2,502 rows)

What happened after each exit. Captures missed peaks and re-entry patterns.

| Column | Type | Description |
|--------|------|-------------|
| `position_id` | INTEGER | PK, foreign key → positions.id |
| `mint` | TEXT | Token mint |
| `symbol` | TEXT | Token symbol |
| `entry_mcap` | REAL | Entry mcap |
| `exit_mcap` | REAL | Exit mcap |
| `exit_reason` | TEXT | Why we exited |
| `closed_at` | TEXT | ISO exit timestamp |
| `post_peak_mcap` | REAL | Highest mcap reached AFTER our exit |
| `post_peak_at_ms` | INTEGER | When post-exit peak happened |
| `post_peak_mult` | REAL | post_peak / exit_mcap. **How much we left on the table** |
| `all_time_peak_mcap` | REAL | Highest mcap ever for this token (across re-entries) |
| `all_time_peak_at_ms` | INTEGER | When all-time peak happened |
| `pre_exit_peak_mcap` | REAL | Peak BEFORE we exited |
| `dead` | INTEGER | Token confirmed dead (0/1) |
| `dead_confirmed_at` | TEXT | When death was confirmed |
| `first_entry_ms` | INTEGER | First time we entered this mint |
| `last_entry_ms` | INTEGER | Most recent re-entry |
| `reentry_count` | INTEGER | How many times we re-entered this token |

---

## screening (17,510 rows)

Tokens rejected by Camus filters that were then watched for future pumping.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | PK |
| `mint` | TEXT | Token mint |
| `symbol` | TEXT | Token symbol |
| `source` | TEXT | Always 'regret_watch' |
| `filter_reasons` | TEXT | Why the filter rejected (comma separated) |
| `entry_mcap_usd` | REAL | MCAP when rejected |
| `created_at` | TEXT | When rejection happened |
| `resolved` | INTEGER | Watch completed? (0/1) |
| `pump_pct_10m` | REAL | % pump in first 10 min after rejection |
| `pump_pct_60m` | REAL | % pump in first 60 min |
| `mcap_at_10m` | REAL | MCAP at 10 min check |
| `mcap_at_60m` | REAL | MCAP at 60 min check |
| `true_ath_mcap` | REAL | All-time highest mcap |
| `ath_missed_multiple` | REAL | ATH / entry_mcap — how many x we missed |
| `resolution` | TEXT | Final verdict: 'pumped' or 'died' |
| `post_call_missed_multiple` | REAL | Alternative missed multiple |
| `is_graduated` | INTEGER | Token graduated? (0/1) |
| `kline_status` | TEXT | Kline pattern status |

---

## simulations (8,312 rows)

5 counterfactual experiments already run against real data.

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | PK |
| `position_id` | INTEGER | Foreign key (may be NULL for mint-level sims) |
| `mint` | TEXT | Token mint |
| `symbol` | TEXT | Token symbol |
| `sim_type` | TEXT | One of: `entry_shadow`, `moonbag`, `runner_mode`, `conviction`, `reentry` |
| `params_json` | TEXT | JSON with sim-specific parameters and results (see GLOSSARY.md) |

### sim_type detail

**entry_shadow** — would a filter rule have blocked this entry?
```json
{"would_block": 1, "block_leg": "kols", "num_kols": 0, "pnl_sol": 0.05}
```

**moonbag** — what if we left 25% to run?
```json
{"moonbag_frac": 0.25, "core_pnl_sol": -0.02, "moonbag_value_sol": 0.15, "vs_full_exit_sol": 0.13}
```

**runner_mode** — what if we held with scale-out tiers?
```json
{"armed_at_ms": 123456, "armed_peak_pct": 175, "shadow_exit_mcap": 500000, "shadow_realized_frac": 2.3}
```

**conviction** — what if we entered at first signal?
```json
{"first_mcap": 15000, "conviction_score": 72, "early_entry_mult": 4.2, "mcap_creep_pct": 40}
```

**reentry** — what if we bought again after exit?
```json
{"exit_mcap": 50000, "resignal_mcap": 35000, "followup_mult": 2.1}
```

---

## enrichment (4,618 rows)

External data attached to tokens: TokenScan (4,192) + AveScan (426).

**TokenScan columns:**
`mint`, `source='tokenscan'`, `fetched_at`, `mcap`, `holder_count`, `liquidity`, `ath_usd`, `ath_drop_pct`, `vol_24h_usd`, `buys_1h`, `sells_1h`, `buy_sell_ratio`, `audit_score`, `top10_holders_pct`, `bundled_pct`, `is_honeypot`, `has_socials`, `hot_rank`, `tier`

**AveScan columns** (same table, different row per mint+source):
`symbol`, `snipers`, `insiders`, `top10_pct`..`top50_pct`, `security_score`, `risk_label`, `no_mint`, `lp_burnt`, `change_15m`, `change_24h`

---

## learning (12,791 rows)

Machine-generated lessons + formal hypotheses from 5,000+ automated analysis runs.

| Column | Type | Description |
|--------|------|-------------|
| `type` | TEXT | 'lesson' or 'hypothesis' or 'hypothesis_run' |
| `title` | TEXT | Hypothesis title (NULL for lessons) |
| `body` | TEXT | Lesson text or hypothesis mechanism |
| `author` | TEXT | 'gadget' or 'human' |
| `status` | TEXT | active/confirmed/falsified/open |
| `metric` | REAL | Hypothesis metric or lesson score |
| `n_size` | INTEGER | Sample size for hypothesis |
| `verdict` | TEXT | confirmed/falsified verdict |
| `evidence` | TEXT | JSON evidence or test SQL |
| `created_at` | TEXT | When created |
| `notes` | TEXT | Additional notes |
