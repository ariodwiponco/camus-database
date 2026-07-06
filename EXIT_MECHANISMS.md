# Camus Exit Configurations

## 1. ADAPTIVE Trail

### What it tracks

ADAPTIVE monitors the position's **trailing peak PnL** — the highest PnL % the token has reached since entry. As the peak grows, ADAPTIVE tightens its trail % to lock in gains. Near breakeven, it loosens to avoid early exits on noise.

### Trigger decision tree

```
For every tick:
  1. Track pnl_peak = max(pnl_percent across all ticks)
  
  2. If pnl_peak >= 50%:
       effective_trail = max(3, base_trail * 0.3)     → trail tightens to ~3%
       Rationale: +50% is a big runner. Tight trail preserves gains.
  
  3. Else if pnl_peak >= 20%:
       effective_trail = max(5, base_trail * 0.6)     → trail tightens to ~6%
       Rationale: Solid move. Moderate tightening.
  
  4. Else if pnl_peak >= 5%:
       effective_trail = base_trail                     → trail stays at 10%
       Rationale: Normal move. Standard trailing.
  
  5. Else if pnl_peak >= 1%:
       effective_trail = base_trail * 1.2               → trail widens to ~12%
       Rationale: Near breakeven. Wider trail prevents noise exits.
  
  6. If (pnl_peak - current_pnl) >= effective_trail:
       → EXIT with reason "ADAPTIVE(n%)"

  7. If current_pnl <= -30%:
       → EXIT with reason "SL(-30%)"

  8. If price drops 70% from HWM within 45s of entry:
       → EXIT with reason "RUG(70%)"

  9. If hold_time >= 135min:
       → EXIT with reason "HOLD(135m)"
```

### Parameters

```json
{
  "type": "adaptive",
  "trail_pct": 10,
  "adaptive": true,
  "sl": -30,
  "rug_drop": 70,
  "rug_window": 45000,
  "max_hold_ms": 8100000
}
```

| Key | Value | Meaning |
|---|---|---|
| trail_pct | 10 | Base trail width (tightens/loosens from here) |
| adaptive | true | Enables the peak-based tightening curve |
| sl | -30 | Hard stop loss if none of the above fired |
| rug_drop | 70 | % drop from HWM that triggers rug exit |
| rug_window | 45000 | Milliseconds from entry to watch for rug |
| max_hold_ms | 8100000 | Hard timeout (135 minutes) |

### Why it wins

Standard TRAIL exits at the same % regardless of context. ADAPTIVE:
- **Captures runners** — at +50% profit, trail tightens to 3%. If price drops 3% from peak, it locks in +47% instead of waiting for a 10% drop that might not come.
- **Avoids noise exits** — at +2% profit, trail widens to 12%. A random 8% dip won't trigger. Standard TRAIL at 10% would exit at -8% (a loss).

---

## 2. Standard TRAIL

### What it tracks

Trailing peak PnL. **Fixed 10% trail** regardless of profit level. Control baseline.

### Trigger decision tree

```
For every tick:
  1. Track pnl_peak = max(pnl_percent across all ticks)
  2. If pnl_peak >= 1% AND (pnl_peak - current_pnl) >= 10%:
       → EXIT with reason "TRAIL"
  3. If current_pnl <= -30%:
       → EXIT with reason "SL(-30%)"
  4. If hold_time >= 135min:
       → EXIT with reason "HOLD(135m)"
```

### Parameters

```json
{
  "type": "trail",
  "trail_pct": 10,
  "trail_arm": 1,
  "sl": -30,
  "max_hold_ms": 8100000
}
```

### When to use

When you want a simple, predictable exit. TRAIL always waits for a 10% drop from peak. No surprises — but also no optimization for different market regimes.

---

## 3. FLOW Exit

### What it tracks

**Buy/sell volume ratio** — NOT price. FLOW watches the flow of money: are buyers still interested, or are insiders dumping while price looks stable?

### Trigger decision tree

```
For every tick:
  1. Track flow_ratio = buy_volume_5m / sell_volume_5m
  2. If flow_ratio < 0.5:
       flow_low_counter += 1
     Else:
       flow_low_counter = 0
  
  3. If flow_low_counter >= 3 AND current_pnl <= 30% AND smart_money < 3:
       → EXIT with reason "FLOW"
       
  4. Standard TRAIL check (same as #2): trailing stop at 10%
  5. SL at -30%, RUG at 70%/45s, HOLD at 135min
```

### Parameters

```json
{
  "type": "flow",
  "trail_pct": 10,
  "trail_arm": 1,
  "sl": -30,
  "flow_ratio": 0.5,
  "flow_ticks": 3,
  "max_hold_ms": 8100000
}
```

| Key | Value | Meaning |
|---|---|---|
| flow_ratio | 0.5 | Exit when sells > 2x buys |
| flow_ticks | 3 | Must be sustained for 3 consecutive ticks |

### When it wins

Tokens that look fine on price but have distribution happening. Price might hold at +5% while smart money sells. FLOW catches this 10 minutes before the price drops.

---

## 4. DOUBLE_SL

### What it tracks

Whether a **price level break** is real or fake. -12% is suspicious (could be a flash crash or shakeout). DOUBLE_SL waits 30s to confirm before exiting.

### Trigger decision tree

```
For every tick:
  1. If pnl_percent <= -12%:
       If this is the first time: start 30s timer
       If timer >= 30s AND still below -12%: → EXIT "SL_TIGHT(-12%)"
       If recovered above -10%: reset timer (was fake)
  
  2. Standard SL at -30% (catches if SL_TIGHT never triggered)
  3. Standard TRAIL at 10% (in case price went up first)
  4. HOLD at 135min
```

### Parameters

```json
{
  "type": "double_sl",
  "sl_tight": -12,
  "sl": -30,
  "trail_pct": 10,
  "max_hold_ms": 8100000
}
```

### When it wins

Tokens that dump hard in the first minute (step function). Standard TRAIL needs a peak to trail from — if price never goes up, TRAIL doesn't arm and the only exit is SL at -30%. DOUBLE_SL catches these 18% earlier.

---

## Testing Against Historical Data

```
                    ADAPTIVE    TRAIL     FLOW    DOUBLE_SL
fee_graduated      +0.947      +0.832    +0.640  -0.721
                    36%/78%     35%/1%    33%/1%   2%/29%

flik_scout         +0.540      +0.216    +0.168  -4.834
                    44%/77%     42%/2%    42%/2%   2%/14%

graduated_trending +0.203      -0.427    -0.521  -17.520
                    44%/79%     43%/4%    42%/1%   2%/19%
```

**Cell:** `Total PnL / WR% / Best%`
- Total PnL = sum across all positions
- WR% = % of profitable exits
- Best% = % of time this mechanism beat all others

**ADAPTIVE wins 77-86% of the time** across all entry routes. DOUBLE_SL destroys PnL on every route tested.

## Deployment

Configs live in `camus_strategies` table:

```sql
INSERT OR REPLACE INTO camus_strategies (id, name, enabled, allocation_pct, config_json) VALUES
('adaptive', 'Adaptive Trail', 1, 100, '{"type":"adaptive","trail_pct":10,"adaptive":true,"sl":-30,"rug_drop":70,"rug_window":45000,"max_hold_ms":8100000}'),
('trail', 'Standard Trail', 1, 100, '{"type":"trail","trail_pct":10,"trail_arm":1,"sl":-30,"max_hold_ms":8100000}'),
('flow', 'Flow Exit', 1, 100, '{"type":"flow","trail_pct":10,"trail_arm":1,"sl":-30,"flow_ratio":0.5,"flow_ticks":3,"max_hold_ms":8100000}'),
('double_sl', 'Double SL', 1, 100, '{"type":"double_sl","sl_tight":-12,"sl":-30,"trail_pct":10,"max_hold_ms":8100000}');
```

Each mechanism runs on every position. First to trigger exits only its slice — the other 3 continue tracking. When all have fired (or 135min timeout), the system compares which mechanism produced the best PnL for that position.
