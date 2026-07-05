# GLOSSARY.md — Domain Terms

## Trading Concepts

### Three-Bucket System
The primary analytical framework. Split all positions into:
- **yielded** (`pnl_sol > 0`): profitable positions. Target: high WR + high avg PnL.
- **dead_entries** (`pnl_sol < -0.01`): losing positions. Target: minimize count and avg loss.
- **middle** (both between): breakeven or fee bleed. Target: minimize.

### Bangers
Tokens that 2x+ (double) from our entry mcap. The key entry signal is `f_obs_missed_mult >= 1.0` — when this fires, the token shows sustained momentum. **~1 banger covers ~6 rug losses.**

### Rugs
Tokens that drop 70%+ from entry. SL fires at -70% floor. 71% of losses happen within 3% of floor — they hit SL hard and fast.

### Capture Ratio
`pnl_sol / reachable_sol`. How much of the available peak-to-peak profit we actually bank. Current: ~14.8% (meaning 85% of potential profit is given back). Target: >30%.

### Exit Signal State
What the state machine decided at each tick:
- `NORMAL`: no action
- `HOLD`: keep holding (smart money present, good vol)
- `EXIT`: signal says sell (distribution, vol dying)
- `EXIT_EMERGENCY`: sell NOW (vol crash, buys frozen)

### Peak-Adaptive Trail
Tightens as peak rises. Current tiers:
- 250%+ peak → 10pp trail (tightest)
- 100-250% → 16pp
- 40-100% → 22pp
- 15-40% → 30pp
- 0-15% → 40pp (widest)

### Flow Ratio
`buy_vol_5m / sell_vol_5m`. < 0.8 = distribution (more selling than buying). > 1.2 = accumulation. A zero-buys-for-2-minutes pattern is structural death.

## Data Concepts

### Shadows
Pre-computed counterfactual simulations. 5 types, each answering a specific question:

1. **entry_shadow**: "Would a new filter rule have blocked this entry?" If blocked_winner, that rule is bad.
2. **moonbag**: "What if we left 25% of each position to keep running?" Compares core_sold + moonbag_hold vs full_exit.
3. **runner_mode**: "What if we held runners with scale-out tiers?" Sell 50% at +150%, 25% at +400%, let rest ride.
4. **conviction**: "What if we entered at first signal (earlier/lower mcap)?" Measures how much extra capture early entry gives.
5. **reentry**: "What if we bought again after exit at a lower mcap?" Measures follow-up potential.

### Forsaken
Tokens that Camus **rejected** (filtered out) which later mooned. These are the painful "what if" cases. Stored in `screening` where `ath_missed_multiple > 1.0`.

### Infirmary
Wounded tokens watched for post-exit recovery. If a token SL'd but then bounced back above entry, it might be worth re-entering. Current SL recovery rate: ~30%.

### Trajectory
Full token lifespan — from first entry through all re-entries to eventual death. Tracks pre-exit peaks, post-exit peaks, and all-time peaks across the entire relationship with a mint.

### Guardrails
Filters that gate entry. The pipeline:
1. **Trending signal** arrives (GMGN hot, fee claim, etc.)
2. **Candidate** created → enters screening
3. **Rejective filters** applied (min_mcap, rugpull, stale-gate, dev_status, regime_throttle, composite-gate)
4. **LLM decision** on remaining candidates
5. **Entry** if approved

### RugCheck Score
External audit score (0-100). Lower = riskier. Applied as a gate for certain routes.

## Metric Cheat Sheet

| Metric | What It Tells You | Good Value |
|--------|------------------|------------|
| `win_rate` | % of positions profitable | >35% |
| `avg_pnl_sol` | Average SOL per position | >0 (positive!) |
| `avg_hold_min` | Average hold duration | 4-15 min (microcaps) |
| `capture_ratio` | % of peak profit banked | >30% |
| `post_peak_mult` | How many x our exit missed | <2.0 (smaller = better) |
| `ath_missed_multiple` | How many x a rejected token did | don't filter out 2x+ tokens |
| `flow_ratio` | Buy/sell pressure | >1.0 healthy |
| `f_obs_missed_mult` | Entry signal strength | ≥1.0 = banger gate |
