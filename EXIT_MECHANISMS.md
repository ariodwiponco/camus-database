# Camus Entry × Exit System

## Design Principle

**Simple data-backed rules beat complex scoring systems.** Each rule is a single observation from 2,474 positions of actual trading history.

## Entry Rules

When a signal arrives, compute entry size:

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

Each tick evaluates:

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

## Performance (backtested on 2,474 positions)

```
                       ENTRY ONLY           ENTRY + EXIT
fee_graduated          +0.013 avg           +0.022 avg
flik_scout             -0.020 avg           +0.008 avg (flow exit saves)
graduated_trending     -0.011 avg           -0.003 avg (still negative)
ALL                    -0.012 avg           +0.006 avg
```

## How to Deploy

Entry rules live in `orchestrator.js` — size computation before creating position.

Exit rules live in `racingManager.js` — each mechanism runs the flow_ratio + smart_money + liquidity checks in addition to its primary logic.

Current racing mechanisms use these rules:
- **PROFIT GUARD**: Uses flow_ratio for bullish hold, flow kill for distribution
- **LIQUIDITY CRASH**: Uses liquidity + sniper + whale signals
- **FLOW KILL**: Uses flow ratio + volume collapse + smart abandonment
- **ADAPTIVE**: Uses flow_ratio + hot_level to adjust trail width
