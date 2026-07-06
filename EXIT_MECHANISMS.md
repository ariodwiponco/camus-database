# Camus Exit Mechanism System

One token entered. **5 exit mechanisms race independently.** Each tracks the same tick data but exits on different conditions. The best mechanism wins more often.

## The 5 Mechanisms

| # | Mechanism | When It Exits | Why Different |
|---|---|---|---|
| 1 | **ADAPTIVE** | Trail tightens: +50% profit→3% trail, BE→12% trail | Adaptive to profit level |
| 2 | **TRAIL** | Fixed 10% trailing from peak | Industry baseline |
| 3 | **FLOW** | Exit when buy/sell < 0.5 for 3 ticks | Catches silent death |
| 4 | **DOUBLE_SL** | -12% tight SL with 30s timer; reset on reclaim | Catches flash dumps |
| 5 | **SUPPRESS** | Exit if below entry for 3min without reclaim | Kills dead tokens |

## Entry × Exit Matrix (2,474 positions)

```
                    ADAPTIVE    TRAIL     FLOW     DOUBLE_SL   SUPPRESS
fee_graduated      +0.947      +0.832    +0.640   -0.721      -1.103
                    36%/78%     35%/1%    33%/1%   2%/29%      2%/35%

flik_scout         +0.540      +0.216    +0.168   -4.834      -6.678
                    44%/77%     42%/2%    42%/2%   2%/14%      2%/40%

graduated_trending +0.203      -0.427    -0.521   -17.520     -28.289
                    44%/79%     43%/4%    42%/1%   2%/19%      6%/29%
```

**Cell:** `Total PnL / WR% / Best%`
- **Total PnL** = sum of all PnL for this combo
- **WR%** = % of positions that closed at profit
- **Best%** = % of time this mechanism beat all others on the same position

## How to Read

**ADAPTIVE** wins ~77-86% of the time. `fee_graduated × ADAPTIVE` = **+0.947 SOL** (36% WR, 78% best rate).

TRAIL/FLOW are similar (both use trailing). DOUBLE_SL/SUPPRESS are destructive on every route.

## DB Tables

```sql
-- Strategy definitions
CREATE TABLE camus_strategies (
  id TEXT PRIMARY KEY,
  name TEXT,
  enabled INTEGER,
  allocation_pct REAL,      -- 100 = full position size
  config_json TEXT          -- JSON with mechanism params
);

-- Position slices (5 per position)
CREATE TABLE position_slices (
  id INTEGER PRIMARY KEY,
  position_id INTEGER,
  strategy_id TEXT,
  size_sol REAL,
  status TEXT,              -- 'active' / 'exited'
  exit_reason TEXT,
  pnl_sol REAL
);

-- Mechanism performance records
CREATE TABLE exit_mechanism_tracker (
  id INTEGER PRIMARY KEY,
  position_id INTEGER,
  entry_route TEXT,          -- e.g. 'fee_graduated'
  mechanism TEXT,            -- e.g. 'ADAPTIVE'
  fired_at_ms INTEGER,
  pnl_at_fire REAL,
  was_actual INTEGER
);
```

## How to Query

```sql
-- Best mechanism per entry route
SELECT entry_route, mechanism,
  ROUND(SUM(pnl_at_fire), 4) AS total_pnl,
  ROUND(AVG(pnl_at_fire), 6) AS avg_pnl,
  COUNT(*) AS n,
  ROUND(SUM(CASE WHEN pnl_at_fire > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS wr
FROM exit_mechanism_tracker
WHERE entry_route IS NOT NULL
GROUP BY entry_route, mechanism
ORDER BY entry_route, total_pnl DESC;

-- Which mechanism had best PnL on each position
WITH ranked AS (
  SELECT position_id, mechanism, pnl_at_fire,
    ROW_NUMBER() OVER (PARTITION BY position_id ORDER BY pnl_at_fire DESC) AS rn
  FROM exit_mechanism_tracker
)
SELECT mechanism, COUNT(*) AS wins
FROM ranked WHERE rn = 1
GROUP BY mechanism ORDER BY wins DESC;
```

## Key Takeaways

1. **ADAPTIVE wins 77-86%** of the time across all routes
2. **Entry route > exit** — fee_graduated vs graduated_trending gap is 1.4 SOL; exit tuning gives 0.12 SOL
3. **Don't hard-block signals** — flik_scout becomes profitable (+0.540) with ADAPTIVE
4. **DOUBLE_SL and SUPPRESS lose money** — included for validation only
5. **All mechanisms simulate from the same tick stream** — no extra API calls needed
