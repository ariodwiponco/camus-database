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

PREPARE EXIT:
  If flow_ratio 0.3 - 0.5:
    → Tighten trail to 3%, prepare exit

HOLD (tight trail):
  If flow_ratio 0.5 - 0.8:
    → Set trail to 8%, normal monitoring

HOLD (loose trail):
  If flow_ratio > 0.8:
    → Set trail to 15%
    If smart_money >= 3: IGNORE trail entirely (they're accumulating)

LIQUIDITY EXIT:
  If liquidity dropped below 5000 AND previously above 20000:
    → EXIT (LP drained, next sell crashes price)

HARD STOPS:
  PnL <= -30% → EXIT (SL)
  hold >= 135min → EXIT (timeout)
```

## The 3 Exit Mechanisms

Each mechanism uses the same signals differently, creating genuine divergence in exit timing and PnL.

### 1. Adaptive Trail

Adjusts trail width based on profit regime AND market conditions.

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

**Config:**
```json
{"type":"adaptive","adaptive":true,"trail_pct":10,"flow_confirm":0.8,"flow_fear":0.3,"hot_tighten":80,"cold_loosen":30,"sl":-30,"max_hold_ms":8100000}
```

### 2. Volume Crash (Liquidity Crash)

Tracks pool health — liquidity, sniper wallets, whale activity. Exits when the market structure collapses regardless of price.

```
TRACK — liquidity peak, sniper wallet count, whale wallet count

A — If liquidity drops 50% from peak → EXIT (LP drained)
B — If sniper wallets spike by 3+ in 60s → EXIT (coordinated attack)
C — If whale wallets drop AND sell volume 3x buy volume → EXIT (whale dump)

HARD — SL at -30%, timeout at 135min
```

**Config:**
```json
{"type":"liquidity_crash","liq_drop_pct":0.5,"sniper_spike":3,"sniper_window_ms":60000,"sl":-30,"max_hold_ms":8100000}
```

### 3. Flow Kill

Monitors volume health and trader behavior. Exits when the token is abandoned regardless of price.

```
TRACK — flow_ratio, total volume (buy + sell), smart_money

A — If flow_ratio < 0.3 for 3 consecutive ticks → EXIT (sustained distribution)
B — If total volume drops to 15% of peak AND flow_ratio < 0.8 → EXIT (volume death)
C — If smart_money = 0 AND flow_ratio < 0.7 AND held > 2min → EXIT (abandoned)

HARD — SL at -30%, timeout at 135min
```

**Config:**
```json
{"type":"flow_kill","flow_kill_ratio":0.3,"flow_kill_ticks":3,"vol_death_pct":0.15,"smart_exit_count":0,"smart_exit_flow":0.7,"smart_exit_delay_ms":120000,"sl":-30,"max_hold_ms":8100000}
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

## Schema

```sql
CREATE TABLE camus_strategies (
  id TEXT PRIMARY KEY,
  name TEXT,
  enabled INTEGER DEFAULT 1,
  allocation_pct REAL,
  config_json TEXT
);

CREATE TABLE position_slices (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  position_id INTEGER NOT NULL,
  strategy_id TEXT NOT NULL,
  size_sol REAL NOT NULL,
  status TEXT DEFAULT 'active',
  exit_reason TEXT,
  pnl_sol REAL
);

CREATE TABLE exit_mechanism_tracker (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  position_id INTEGER NOT NULL,
  entry_route TEXT,
  mechanism TEXT NOT NULL,
  pnl_at_fire REAL,
  was_actual INTEGER DEFAULT 0
);
```

## Key Takeaways

1. **ADAPTIVE trail wins 77-86%** of the time across all entry routes
2. **Entry route matters more than exit** — fee_graduated vs graduated_trending gap is 1.4 SOL
3. **Flow ratio is the best exit signal** — < 0.3 = emergency, > 0.8 = ride it
4. **Liquidity >= 20K predicts 34% WR** — size up when pool is deep
