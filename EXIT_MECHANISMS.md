# Camus Entry × Exit System

## Design Principle

**Simple data-backed rules beat complex scoring systems.** Each rule is a single observation from 2,474 positions of actual trading history.

## Entry Sizing

When a signal arrives, compute entry size based on route and liquidity:

```
score = 0

Route bonus (strongest predictor):
  fee_graduated           → +0.05 SOL  (avg +0.013, 30% WR, N=166)
  fee_graduated_trending  → +0.05 SOL  (avg +0.004, 32% WR, N=151)
  flik_scout/grad_trending→ +0.00 SOL  (avg -0.011 to -0.020, 28% WR)
  fee_trending            → -0.02 SOL  (avg -0.024, 25% WR)

Liquidity bonus (second strongest):
  >= 50K USD  → +0.10 SOL  (avg +0.022, 44% WR, N=55)
  20K - 50K   → +0.05 SOL  (avg +0.001, 34% WR, N=855)
  10K - 20K   → +0.00 SOL  (avg -0.013, 27% WR, N=2276)
  < 10K       → -0.05 SOL  (avg -0.018, 22% WR, N=560)

base = 0.10 SOL
final = clamp(base + score, min=0.02, max=0.25)
```

## Exit Rules

Each tick evaluates the following signals in order:

```
flow_ratio = buy_vol_5m / sell_vol_5m
smart_money = smart_money_count  
liquidity = pool_liquidity_usd

EMERGENCY EXIT:
  If flow_ratio < 0.3:
    → EXIT immediately (avg PnL -16.6%, WR 22%)
    Rationale: Sellers overwhelming. Price will crash shortly.

PREPARE EXIT:
  If flow_ratio 0.3 - 0.5:
    → Tighten trail to 3%, prepare exit
    Rationale: Distribution in progress. Average PnL -6.5%.

HOLD (tight trail):
  If flow_ratio 0.5 - 0.8:
    → Set trail to 8%, normal monitoring
    Rationale: Mixed signals. Avg PnL +3%, WR 39%.

HOLD (loose trail):
  If flow_ratio > 0.8:
    → Set trail to 15%
    Rationale: Buyers dominate. Avg PnL +14%, WR 48%.
    If smart_money >= 3: IGNORE trail entirely (they're accumulating)

LIQUIDITY EXIT:
  If liquidity dropped below 5000 AND previously above 20000:
    → EXIT (LP drained, next sell crashes price)

HARD STOPS:
  PnL <= -30% → EXIT (SL)
  hold >= 135min → EXIT (timeout)
```

## The 4 Racing Mechanisms

Each mechanism uses the same signals differently, creating genuine divergence:

### 1. Profit Guard
```
PHASE 1 — First TP at +50% → sell 70%, keep 30% moonbag
PHASE 2 — Runner tiers: +150% sell half, +400% sell quarter
PHASE 3 — Bullish hold: if flow_ratio >= 0.8 AND smart >= 3, extend hold
PHASE 4 — Flow kill: if flow_ratio < 0.3, exit remaining
PHASE 5 — Standard trail at 10% on remaining position
HARD — SL at -30%, timeout at 135min
```

### 2. Liquidity Crash
```
TRACK — liquidity peak, sniper wallet count, whale wallet count

A — If liquidity drops 50% from peak → EXIT (LP drained)
B — If sniper wallets spike by 3+ in 60s → EXIT (coordinated attack)
C — If whale wallets drop AND sell volume 3x buy volume → EXIT (whale dump)

HARD — SL at -30%, timeout at 135min
```

### 3. Flow Kill
```
TRACK — flow_ratio, total volume (buy + sell), smart_money

A — If flow_ratio < 0.3 for 3 consecutive ticks → EXIT (sustained distribution)
B — If total volume drops to 15% of peak AND flow_ratio < 0.8 → EXIT (volume death)
C — If smart_money = 0 AND flow_ratio < 0.7 AND held > 2min → EXIT (abandoned)

HARD — SL at -30%, timeout at 135min
```

### 4. Adaptive Trail
```
TRACK — pnl_peak, flow_ratio, hot_level

BASE TRAIL from profit regime:
  pnl_peak >= 50% → trail = 3%
  pnl_peak >= 20% → trail = 6%
  pnl_peak >= 5%  → trail = 10%
  pnl_peak >= 1%  → trail = 12%

ADJUST by flow:
  flow >= 0.8 → trail *= 1.5 (buyers confirm move, let it run)
  flow < 0.3  → trail *= 0.7 (distribution, tighten)

ADJUST by volatility:
  hot >= 80 → trail *= 0.8 (memes reverse fast)
  hot < 30  → trail *= 1.2 (slow move needs room)

EXIT if (pnl_peak - current_pnl) >= adjusted_trail

HARD — SL at -30%, timeout at 135min
```

## Data Sources

All mechanisms read from the same tick stream (`position_ticks` table):

| Column | What it measures |
|---|---|
| `mcap` | Current market cap |
| `pnl_percent` | PnL % from entry |
| `drawdown_pct` | % below peak |
| `flow_ratio` | buy_vol_5m / sell_vol_5m |
| `buys_5m` / `sells_5m` | Buy/sell tx count (5min) |
| `buy_vol_5m` / `sell_vol_5m` | Volume in SOL |
| `smart_money` | Smart money wallets active |
| `holder_count` | Current holder count |
| `liquidity` | Pool liquidity in USD |
| `sniper_wallets` / `whale_wallets` | Wallet type counts |
| `hot_level` | GMGN hotness score |
| `dev_status` | Dev activity: holding/selling/dumped |

No extra API calls. Every mechanism derives from the same tick data.

## Deployment

Configs live in `camus_strategies` table. Each mechanism runs on every position:

```sql
INSERT OR REPLACE INTO camus_strategies (id, name, enabled, allocation_pct, config_json) VALUES
('profit_guard', 'Profit Guard', 1, 100, '{"type":"profit_guard","tp_pct":50,"tp_sell_frac":0.7,"moonbag_frac":0.3,"trail_pct":10,"sl":-30,"bullish_flow":0.8,"flow_kill":0.3,"max_hold_ms":8100000}'),
('liquidity_crash', 'Liquidity Crash', 1, 100, '{"type":"liquidity_crash","liq_drop_pct":0.5,"sniper_spike":3,"sniper_window_ms":60000,"sl":-30,"max_hold_ms":8100000}'),
('flow_kill', 'Flow Kill', 1, 100, '{"type":"flow_kill","flow_kill_ratio":0.3,"flow_kill_ticks":3,"vol_death_pct":0.15,"smart_exit_count":0,"smart_exit_flow":0.7,"smart_exit_delay_ms":120000,"sl":-30,"max_hold_ms":8100000}'),
('adaptive', 'Adaptive Trail', 1, 100, '{"type":"adaptive","adaptive":true,"trail_pct":10,"flow_confirm":0.8,"flow_fear":0.3,"hot_tighten":80,"cold_loosen":30,"sl":-30,"max_hold_ms":8100000}');
```

Each position creates 4 slices (one per mechanism). The first to trigger only exits its slice — the other 3 keep tracking. After all have fired or 135min timeout, the system compares which mechanism had the best PnL for that position.
