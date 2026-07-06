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

## Entry × Exit Performance (from 2,474 positions)

```
                    ADAPTIVE    TRAIL     FLOW     DOUBLE_SL   SUPPRESS
fee_graduated      +0.947      +0.832    +0.640   -0.721      -1.103
                    36%/78%     35%/1%    33%/1%   2%/29%      2%/35%

flik_scout         +0.540      +0.216    +0.168   -4.834      -6.678
                    44%/77%     42%/2%    42%/2%   2%/14%      2%/40%

graduated_trending +0.203      -0.427    -0.521   -17.520     -28.289
                    44%/79%     43%/4%    42%/1%   2%/19%      6%/29%
```

**Cell format:** Total PnL / WR% / Best%
- **Total PnL** = sum of all PnL for this combo
- **WR%** = % of positions that closed at profit
- **Best%** = % of time this mechanism beat all others

ADAPTIVE wins ~77-86% of the time across all routes. DOUBLE_SL and SUPPRESS destroy PnL on every route.

## Data Sources

All signals derived from `position_ticks` table — no extra API calls:

| Column | What it measures |
|---|---|
| `flow_ratio` | buy_vol_5m / sell_vol_5m |
| `smart_money` | Smart money wallets active |
| `liquidity` | Pool liquidity in USD |
| `sniper_wallets` / `whale_wallets` | Wallet type counts |
| `hot_level` | GMGN hotness score |

## Schema

```sql
-- Strategy definitions (one per mechanism)
CREATE TABLE camus_strategies (
  id TEXT PRIMARY KEY,
  name TEXT,
  enabled INTEGER DEFAULT 1,
  allocation_pct REAL,
  config_json TEXT
);

-- Position slices (one per strategy per position)
CREATE TABLE position_slices (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  position_id INTEGER NOT NULL,
  strategy_id TEXT NOT NULL,
  size_sol REAL NOT NULL,
  status TEXT DEFAULT 'active',
  exit_reason TEXT,
  pnl_sol REAL
);

-- Mechanism performance records
CREATE TABLE exit_mechanism_tracker (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  position_id INTEGER NOT NULL,
  entry_route TEXT,
  mechanism TEXT NOT NULL,
  pnl_at_fire REAL,
  was_actual INTEGER DEFAULT 0
);

-- Entry × Exit weights (computed from exit_mechanism_tracker)
CREATE TABLE entry_exit_weights (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entry_route TEXT NOT NULL,
  exit_mechanism TEXT NOT NULL,
  weight REAL DEFAULT 1.0,
  total_pnl REAL DEFAULT 0,
  n_positions INTEGER DEFAULT 0,
  best_count INTEGER DEFAULT 0,
  wr REAL DEFAULT 0,
  UNIQUE(entry_route, exit_mechanism)
);
```

## Key Takeaways

1. **ADAPTIVE trail wins 77-86%** of the time across all entry routes
2. **Entry route matters more than exit** — fee_graduated vs graduated_trending gap is 1.4 SOL; exit tuning gives 0.12 SOL
3. **Flow ratio is the best exit signal** — < 0.3 = emergency, > 0.8 = ride it
4. **Liquidity >= 20K predicts 34% WR** — size up when pool is deep
5. **Don't hard-block signals** — flik_scout becomes profitable (+0.540) with ADAPTIVE
