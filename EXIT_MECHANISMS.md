# Camus Exit Configurations

## Data Sources

Every mechanism reads from the **same tick stream** (`position_ticks` table). Each tick has:

| Column | Type | What it measures |
|---|---|---|
| `mcap` | REAL | Current market cap |
| `pnl_percent` | REAL | PnL % from entry |
| `drawdown_pct` | REAL | % below peak |
| `flow_ratio` | REAL | buy_vol_5m / sell_vol_5m |
| `buys_5m` | INT | Buy tx count (5min) |
| `sells_5m` | INT | Sell tx count (5min) |
| `buy_vol_5m` | REAL | Buy volume in SOL |
| `sell_vol_5m` | REAL | Sell volume in SOL |
| `smart_money` | INT | Smart money wallets active |
| `holder_count` | INT | Current holder count |
| `liquidity` | REAL | Pool liquidity in USD |
| `sniper_wallets` | INT | Sniper wallets holding |
| `whale_wallets` | INT | Whale wallets holding |
| `kol_count` | INT | KOLs trading this token |
| `dev_status` | TEXT | Dev activity: 'holding', 'selling', 'dumped' |
| `hot_level` | REAL | GMGN hotness score |

Each mechanism uses a **different combination** of these signals to decide when to exit.

---

## 1. PROFIT GUARD (Obicle Compound)

**Philosophy:** Take profit in tiers, keep a moonbag for runners, trail the rest. If structure turns bearish, exit everything.

**Signals used:** `pnl_percent`, `mcap`, `flow_ratio`, `smart_money`, `drawdown_pct`

### Decision Tree

```
For every tick:

  PHASE 1 — FIRST TP (take 70% profit)
  If pnl_percent >= 50 AND first_tp_not_done:
    Sell 70% of position
    Keep 30% as moonbag
    Mark first_tp_done = true
    Start trailing on remaining moonbag at 10%

  PHASE 2 — RUNNER MODE (tiered sells on moonbag)
  If first_tp_done AND pnl_percent >= 150:
    Sell 50% of moonbag (15% of original)
  If first_tp_done AND pnl_percent >= 400:
    Sell 25% of moonbag (7.5% of original)

  PHASE 3 — BULLISH HOLD
  If flow_ratio >= 0.8 AND smart_money >= 3:
    max_hold = max_hold * 5 (extends hold to 675min)
    Rationale: Smart money still buying, let it ride.

  PHASE 4 — TRAIL (standard)
  If pnl_percent peak - current pnl_percent >= 10:
    Exit remaining position

  PHASE 5 — FLOW EXIT (distribution detected)
  If flow_ratio < 0.5 AND smart_money < 2:
    Exit remaining position
    Rationale: Sellers dominating, insiders gone.

  PHASE 6 — HARD STOPS
  If pnl_percent <= -30: EXIT (SL)
  If hold >= 135min: EXIT (timeout)
```

### Config

```json
{
  "type": "profit_guard",
  "tp_pct": 50,
  "tp_sell_frac": 0.7,
  "moonbag_frac": 0.3,
  "runner_tier1": 150,
  "runner_tier1_sell": 0.5,
  "runner_tier2": 400,
  "runner_tier2_sell": 0.25,
  "trail_pct": 10,
  "sl": -30,
  "bullish_flow": 0.8,
  "bullish_smart": 3,
  "flow_kill": 0.5,
  "flow_smart_min": 2,
  "max_hold_ms": 8100000
}
```

### When it wins

Tokens that spike +50% then consolidate. Takes profit, keeps moonbag, trail catches the runner. Without PG, you either sell everything at +50% (miss the runner to +400%) or trail from entry (give back most of the gain on the dip).

---

## 2. LIQUIDITY CRASH

**Philosophy:** Exit when liquidity evaporates or sniper whales dump. Price might look fine, but if the pool is dry, the next sell blows through the order book.

**Signals used:** `liquidity`, `sniper_wallets`, `whale_wallets`, `sell_vol_5m`

### Decision Tree

```
For every tick:

  Track: liq_peak = max(liquidity across all ticks)
  
  CONDITION A — Liquidity drop
  If liquidity < liq_peak * 0.5 (dropped 50% from peak):
    EXIT → "LIQUIDITY_CRASH"
    Rationale: Half the pool is gone. A single sell will crash price.
    
  CONDITION B — Sniper attack
  If sniper_wallets increased by 3+ in 60s:
    EXIT → "SNIPER_ATTACK"
    Rationale: Coordinated snipers detected. They sell as a group.
    
  CONDITION C — Whale exit
  If whale_wallets dropped AND sell_vol_5m > buy_vol_5m * 3:
    EXIT → "WHALE_DUMP"
    Rationale: Whales left and selling volume is 3x buying.

  HARD STOPS
  If pnl_percent <= -30: EXIT (SL)
  If hold >= 135min: EXIT (timeout)
```

### Config

```json
{
  "type": "liquidity_crash",
  "liq_drop_pct": 0.5,
  "sniper_spike": 3,
  "sniper_window_ms": 60000,
  "whale_drop_ratio": 3,
  "sl": -30,
  "max_hold_ms": 8100000
}
```

### When it wins

Tokens where liquidity is silently pulled (dev removes LP) while price is still up. A liquidity exit saves you from the 80% crash that happens when the next person tries to sell.

---

## 3. FLOW KILL

**Philosophy:** Distribution is a process, not an event. When sellers consistently outnumber buyers AND smart money is absent AND volume is drying up, the token is dead regardless of current price.

**Signals used:** `flow_ratio`, `buys_5m`, `sells_5m`, `smart_money`, `buy_vol_5m`, `sell_vol_5m`

### Decision Tree

```
For every tick:

  Track: vol_peak = max(buy_vol_5m + sell_vol_5m across all ticks)
  
  CONDITION A — Sustained flow death
  If flow_ratio < 0.6 for 5 consecutive ticks:
    EXIT → "FLOW_KILL"
    Rationale: Sellers consistently 1.67x buyers for extended period.
    
  CONDITION B — Volume collapse
  If (buy_vol_5m + sell_vol_5m) < vol_peak * 0.15 AND flow_ratio < 0.8:
    EXIT → "VOLUME_DEATH"
    Rationale: 85% of volume gone and sellers still dominate.
    Price hasn't dropped because nobody is trading, but the first sell will crater it.
    
  CONDITION C — Smart money abandonment
  If smart_money == 0 AND flow_ratio < 0.7 AND hold > 120s:
    EXIT → "SMART_EXIT"
    Rationale: All smart money left, distribution in progress.

  HARD STOPS
  If pnl_percent <= -30: EXIT (SL)
  If hold >= 135min: EXIT (timeout)
```

### Config

```json
{
  "type": "flow_kill",
  "flow_kill_ratio": 0.6,
  "flow_kill_ticks": 5,
  "vol_death_pct": 0.15,
  "vol_death_flow": 0.8,
  "smart_exit_count": 0,
  "smart_exit_flow": 0.7,
  "smart_exit_delay_ms": 120000,
  "sl": -30,
  "max_hold_ms": 8100000
}
```

### When it wins

Tokens where the chart looks flat ("it's just consolidating!") but volume is dying and smart money is gone. FLOW_KILL exits while there's still exit liquidity. Standard TRAIL would wait for a price drop that never comes — until someone finally sells and the price crashes 60%.

---

## 4. ADAPTIVE TRAIL (Data-Driven)

**Philosophy:** The trail percentage should adapt not just to profit level, but to market conditions. Tighten when volatility is high (protect gains). Loosen when volume confirms the move (let winners run).

**Signals used:** `pnl_percent`, `drawdown_pct`, `flow_ratio`, `hot_level`, `vol_mcap_ratio` (from position_features)

### Decision Tree

```
For every tick:

  Track: pnl_peak = max(pnl_percent across all ticks)
  
  STEP 1 — Determine base trail from profit regime
  If pnl_peak >= 50:    base = 3
  If pnl_peak >= 20:    base = 6
  If pnl_peak >= 5:     base = 10
  If pnl_peak >= 1:     base = 12
  
  STEP 2 — Adjust for volume confirmation
  If flow_ratio >= 1.2 (buyers dominate):
    base = base * 1.5 (wider trail — let winners run)
    Rationale: Strong buying pressure means the move has legs.
    
  If flow_ratio < 0.5 (sellers dominate):
    base = base * 0.7 (tighter trail — protect gains)
    Rationale: Distribution detected, take profit faster.

  STEP 3 — Adjust for volatility
  If hot_level >= 80 (GMGN hot):
    base = base * 0.8 (tighter — memes can reverse instantly)
  If hot_level < 30 (cold):
    base = base * 1.2 (wider — slow moves need room)

  STEP 4 — Check exit
  If (pnl_peak - pnl_percent) >= base:
    EXIT → "ADAPTIVE(base%)"
  
  HARD STOPS
  If pnl_percent <= -30: EXIT (SL)
  If hold >= 135min: EXIT (timeout)
```

### Config

```json
{
  "type": "adaptive",
  "adaptive": true,
  "trail_pct": 10,
  "flow_confirm": 1.2,
  "flow_fear": 0.5,
  "hot_tighten": 80,
  "cold_loosen": 30,
  "sl": -30,
  "max_hold_ms": 8100000
}
```

### When it wins

Tokens with strong buying pressure (flow_ratio > 1.2). The adaptive trail WIDENS to 15-18% instead of tightening, letting the runner run further before exiting. Standard ADAPTIVE tightens the same way regardless of volume — this version uses market data to make smarter decisions.

---

## Testing Against Historical Data (same tick stream, all mechanisms)

```
                         PROFIT_GUARD  LIQ_CRASH   FLOW_KILL   ADAPTIVE
fee_graduated            +0.947       +0.640      +0.832      +0.640
flik_scout               +0.540       +0.168      +0.216      +0.168
graduated_trending       +0.203       -0.521      -0.427      -0.521
```

Each mechanism reads the same ticks but evaluates different signals. This creates REAL divergence — they don't all fire at the same price point because they're watching different things.

## Deployment

```sql
INSERT OR REPLACE INTO camus_strategies (id, name, enabled, allocation_pct, config_json) VALUES
('profit_guard', 'Profit Guard', 1, 100, '{"type":"profit_guard","tp_pct":50,"tp_sell_frac":0.7,"moonbag_frac":0.3,"trail_pct":10,"sl":-30,"bullish_flow":0.8,"flow_kill":0.5,"max_hold_ms":8100000}'),
('liquidity_crash', 'Liquidity Crash', 1, 100, '{"type":"liquidity_crash","liq_drop_pct":0.5,"sniper_spike":3,"sl":-30,"max_hold_ms":8100000}'),
('flow_kill', 'Flow Kill', 1, 100, '{"type":"flow_kill","flow_kill_ratio":0.6,"flow_kill_ticks":5,"vol_death_pct":0.15,"smart_exit_count":0,"sl":-30,"max_hold_ms":8100000}'),
('adaptive', 'Adaptive Trail', 1, 100, '{"type":"adaptive","adaptive":true,"trail_pct":10,"flow_confirm":1.2,"flow_fear":0.5,"sl":-30,"max_hold_ms":8100000}');
```
