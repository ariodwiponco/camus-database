# QUERIES.md — Ready-to-Run Analysis SQL

All queries target `camus-warehouse.db`.

## 1. Baseline Performance

```sql
-- Win rate, avg PnL, total PnL
SELECT
  COUNT(*) n,
  ROUND(SUM(CASE WHEN pnl_sol > 0 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) wr,
  ROUND(AVG(pnl_sol),4) avg_pnl,
  ROUND(SUM(pnl_sol),2) total_pnl,
  ROUND(AVG(hold_ms/60000.0),1) avg_hold_min
FROM positions;
```

```sql
-- Three-bucket
SELECT CASE WHEN pnl_sol > 0 THEN 'yielded'
       WHEN pnl_sol < -0.01 THEN 'dead_entries'
       ELSE 'middle' END bucket,
  COUNT(*) n,
  ROUND(SUM(pnl_sol),2) total_pnl,
  ROUND(AVG(pnl_sol),4) avg_pnl,
  ROUND(AVG(hold_ms/60000.0),1) hold_min
FROM positions
GROUP BY bucket;
```

## 2. Exit Analysis

```sql
-- Performance by exit reason
SELECT exit_reason,
  COUNT(*) n,
  ROUND(AVG(pnl_sol),4) avg_pnl,
  ROUND(SUM(pnl_sol),2) total_pnl,
  ROUND(SUM(CASE WHEN pnl_sol>0 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) wr,
  ROUND(AVG(hold_ms/60000.0),1) hold_min,
  ROUND(AVG(peak_pct),1) avg_peak_pct
FROM positions
WHERE exit_reason NOT LIKE 'VOIDED%'
GROUP BY exit_reason
ORDER BY total_pnl;
```

```sql
-- Exit signal state performance
SELECT exit_signal_state, COUNT(*) n,
  ROUND(AVG(pnl_sol),4) avg_pnl,
  ROUND(SUM(CASE WHEN pnl_sol>0 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) wr
FROM positions
WHERE exit_signal_state IS NOT NULL
GROUP BY exit_signal_state;
```

## 3. Entry Feature Analysis

```sql
-- Worst-performing entry feature = f_hot_level
SELECT CASE
  WHEN f_hot_level < 10 THEN '0-9'
  WHEN f_hot_level < 20 THEN '10-19'
  WHEN f_hot_level < 40 THEN '20-39'
  WHEN f_hot_level < 70 THEN '40-69'
  ELSE '70+' END hot_bucket,
  COUNT(*) n,
  ROUND(AVG(pnl_sol),4) avg_pnl,
  ROUND(SUM(CASE WHEN pnl_sol>0 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) wr,
  ROUND(AVG(peak_pct),1) avg_peak
FROM positions
GROUP BY hot_bucket;
```

```sql
-- f_obs_missed_mult gate analysis
SELECT CASE WHEN f_obs_missed_mult >= 1.0 THEN 'gate_passed' ELSE 'gate_blocked' END gate,
  COUNT(*) n,
  ROUND(SUM(CASE WHEN pnl_sol>0 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) wr,
  ROUND(AVG(pnl_sol),4) avg_pnl,
  ROUND(SUM(pnl_sol),2) total_pnl
FROM positions
GROUP BY gate;
```

```sql
-- Entry mcap bucket analysis
SELECT CASE
  WHEN entry_mcap < 20000 THEN 'micro (<$20K)'
  WHEN entry_mcap < 50000 THEN 'small ($20-50K)'
  WHEN entry_mcap < 100000 THEN 'mid ($50-100K)'
  WHEN entry_mcap < 200000 THEN 'large ($100-200K)'
  ELSE 'mega ($200K+)' END mcap_bucket,
  COUNT(*) n,
  ROUND(AVG(pnl_sol),4) avg_pnl,
  ROUND(SUM(CASE WHEN pnl_sol>0 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) wr
FROM positions
GROUP BY mcap_bucket
ORDER BY avg_pnl;
```

## 4. Capture Analysis

```sql
-- Capture ratio by peak tier
SELECT CASE
  WHEN peak_pct < 50 THEN 'flat (<50%)'
  WHEN peak_pct < 100 THEN 'mid (50-100%)'
  WHEN peak_pct < 150 THEN 'hot (100-150%)'
  ELSE 'runner (150%+)' END bucket,
  COUNT(*) n,
  ROUND(AVG(capture_ratio),2) avg_capture,
  ROUND(AVG(missed_multiple),2) avg_missed_mult,
  ROUND(AVG(peak_pct),1) avg_peak,
  ROUND(AVG(pnl_sol),4) avg_pnl
FROM positions
WHERE capture_ratio IS NOT NULL AND exit_reason NOT LIKE 'VOIDED%'
GROUP BY bucket;
```

## 5. Time-Based Patterns

```sql
-- Performance by hold duration
SELECT CASE
  WHEN hold_ms < 300000 THEN '0-5min'
  WHEN hold_ms < 600000 THEN '5-10min'
  WHEN hold_ms < 900000 THEN '10-15min'
  WHEN hold_ms < 1800000 THEN '15-30min'
  ELSE '30min+' END hold_bucket,
  COUNT(*) n,
  ROUND(AVG(pnl_sol),4) avg_pnl,
  ROUND(SUM(CASE WHEN pnl_sol>0 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) wr,
  ROUND(AVG(peak_pct),1) avg_peak
FROM positions
WHERE hold_ms IS NOT NULL
GROUP BY hold_bucket;
```

## 6. Post-Mortem Regret

```sql
-- Top 20 misses: positions where ATH was MUCH higher than our exit
SELECT p.mint, p.symbol,
  ROUND(p.entry_mcap) entry, ROUND(p.exit_mcap) exit,
  ROUND(pm.post_peak_mult,1) left_on_table_x,
  ROUND(pm.all_time_peak_mcap) all_time_peak,
  ROUND(p.pnl_sol,3) pnl_sol,
  ROUND(p.peak_pct,1) peak_pct,
  p.exit_reason
FROM positions p
JOIN post_mortem pm ON pm.position_id = p.id
WHERE pm.post_peak_mult > 3 AND p.pnl_sol < 0
ORDER BY pm.post_peak_mult DESC
LIMIT 20;
```

## 7. Screening (Rejected Tokens)

```sql
-- What % of rejected tokens hit 2x+?
SELECT
  COUNT(*) total_rejected,
  ROUND(SUM(CASE WHEN true_ath_mcap / NULLIF(entry_mcap_usd,0) >= 2 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) pct_2x_plus,
  ROUND(AVG(true_ath_mcap / NULLIF(entry_mcap_usd,0)),2) avg_missed_mult,
  ROUND(SUM(CASE WHEN resolution = 'pumped' THEN 1 ELSE 0 END)*100.0/COUNT(*),1) pct_verdict_pumped
FROM screening;
```

```sql
-- Which filter catches most bangers (blocks tokens that later do 2x+)?
SELECT filter_reasons, COUNT(*) n,
  ROUND(SUM(CASE WHEN true_ath_mcap / NULLIF(entry_mcap_usd,0) >= 2 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) pct_2x_plus
FROM screening
WHERE filter_reasons != ''
GROUP BY filter_reasons
HAVING n >= 50
ORDER BY pct_2x_plus DESC;
```

## 8. Simulations

```sql
-- Moonbag: how much extra SOL would moonbag strategy yield?
SELECT
  COUNT(*) n,
  ROUND(SUM(CAST(JSON_EXTRACT(params_json, '$.vs_full_exit_sol') AS REAL)),2) extra_sol,
  ROUND(AVG(CAST(JSON_EXTRACT(params_json, '$.vs_full_exit_sol') AS REAL)),4) avg_extra_per_trade
FROM simulations
WHERE sim_type = 'moonbag';
```

```sql
-- Conviction: early entry multiple
SELECT
  ROUND(AVG(CAST(JSON_EXTRACT(params_json, '$.early_entry_mult') AS REAL)),2) avg_early_mult,
  ROUND(MAX(CAST(JSON_EXTRACT(params_json, '$.early_entry_mult') AS REAL)),1) best_early_mult
FROM simulations
WHERE sim_type = 'conviction';
```

## 9. Learning

```sql
-- Most important lessons
SELECT body, metric, n_size, verdict
FROM learning
WHERE type = 'hypothesis' AND status = 'confirmed'
ORDER BY n_size DESC
LIMIT 10;
```

```sql
-- All active lessons
SELECT body, created_at
FROM learning
WHERE type = 'lesson' AND status = 'active'
ORDER BY created_at DESC;
```

## 10. Archetype Analysis

```sql
-- Archetype performance
SELECT archetype,
  COUNT(*) n,
  ROUND(AVG(pnl_sol),4) avg_pnl,
  ROUND(AVG(peak_pct),1) avg_peak,
  ROUND(AVG(hold_ms/60000.0),1) hold_min,
  ROUND(SUM(CASE WHEN pnl_sol>0 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) wr
FROM positions
WHERE archetype IS NOT NULL
GROUP BY archetype
ORDER BY avg_pnl DESC;
```
