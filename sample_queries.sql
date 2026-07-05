-- Sample SQL Queries for Camus Warehouse
-- Run: sqlite3 data/camus-warehouse.db < sample_queries.sql

.mode column
.headers on
.width 20 8 10 10 10

-- 1. Overall performance
SELECT '=== OVERALL ===' as '';
SELECT COUNT(*) as trades,
  ROUND(AVG(pnl_sol),4) as avg_pnl,
  ROUND(SUM(pnl_sol),2) as total_pnl,
  ROUND(SUM(CASE WHEN pnl_sol>0 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) as wr
FROM positions;

-- 2. Three bucket
SELECT '=== THREE-BUCKET ===' as '';
SELECT CASE WHEN pnl_sol > 0 THEN 'yielded'
       WHEN pnl_sol < -0.01 THEN 'dead'
       ELSE 'middle' END as bucket,
  COUNT(*) as n,
  ROUND(AVG(pnl_sol),4) as avg_pnl,
  ROUND(SUM(pnl_sol),2) as total_pnl
FROM positions GROUP BY bucket;

-- 3. Exit breakdown
SELECT '=== EXIT REASONS ===' as '';
SELECT exit_reason, COUNT(*) as n,
  ROUND(AVG(pnl_sol),4) as avg_pnl,
  ROUND(SUM(CASE WHEN pnl_sol>0 THEN 1 ELSE 0 END)*100.0/COUNT(*),1) as wr
FROM positions WHERE exit_reason NOT LIKE 'VOIDED%'
GROUP BY exit_reason ORDER BY n DESC;

-- 4. Archetype performance
SELECT '=== ARCHETYPES ===' as '';
SELECT archetype, COUNT(*) as n,
  ROUND(AVG(pnl_sol),4) as avg_pnl,
  ROUND(AVG(peak_pct),1) as peak
FROM positions WHERE archetype IS NOT NULL
GROUP BY archetype ORDER BY avg_pnl DESC;

-- 5. Hold time
SELECT '=== HOLD TIME BUCKETS ===' as '';
SELECT CASE
  WHEN hold_ms < 300000 THEN '0-5min'
  WHEN hold_ms < 600000 THEN '5-10min'
  WHEN hold_ms < 1800000 THEN '10-30min'
  ELSE '30min+' END as hold,
  COUNT(*) as n,
  ROUND(AVG(pnl_sol),4) as avg_pnl,
  ROUND(AVG(peak_pct),1) as avg_peak
FROM positions WHERE hold_ms IS NOT NULL
GROUP BY hold;
