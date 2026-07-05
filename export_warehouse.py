#!/usr/bin/env python3
"""
Camus Warehouse Export — transforms 47-table operational DB → 7-table clean schema.
Run on the source server, outputs a compact analytical database.
"""
import sqlite3, os, sys, json
from datetime import datetime, timezone

SRC = "camus-copy.sqlite"
DST = "data/camus-warehouse.db"

def ms2iso(ms):
    if not ms or ms == 0: return None
    return datetime.fromtimestamp(ms/1000, tz=timezone.utc).isoformat()

def connect(src):
    con = sqlite3.connect(src)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=OFF")  # speed up reads
    con.execute("PRAGMA synchronous=OFF")
    return con

def create_dst(con):
    con.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;

        CREATE TABLE positions (
            id                INTEGER PRIMARY KEY,
            mint              TEXT NOT NULL,
            symbol            TEXT,
            strategy_id       TEXT,
            route             TEXT,

            -- timing
            opened_at         TEXT,          -- ISO timestamp
            closed_at         TEXT,
            hold_ms           INTEGER,

            -- sizing
            size_sol          REAL,
            calibrated_size_sol REAL,
            slippage_pct      REAL,
            slippage_cost_sol REAL,
            gross_pnl_sol     REAL,
            gross_pnl_percent REAL,
            net_pnl_sol       REAL,
            pnl_sol           REAL,
            pnl_percent       REAL,

            -- entry / exit prices
            entry_mcap        REAL,
            entry_price       REAL,
            exit_mcap         REAL,
            exit_price        REAL,
            high_water_mcap   REAL,
            low_water_mcap    REAL,
            exit_reason       TEXT,

            -- exit signal details (from retreat_log)
            exit_signal_state       TEXT,    -- NORMAL|EXIT|EXIT_EMERGENCY|HOLD
            exit_signal_debounced   TEXT,
            dynamic_trail_pct       REAL,
            flow_ratio              REAL,
            smart_money             INTEGER,
            smart_trend             TEXT,
            tokenscan_composite     INTEGER,
            exit_tag                TEXT,

            -- entry features (f_* from dry_run_positions)
            f_route             TEXT,
            f_hot_level         REAL,
            f_smart_count       REAL,
            f_obs_missed_mult   REAL,
            f_holder_count      REAL,
            f_fresh_rate        REAL,
            f_gmgn_fees_sol     REAL,
            f_kol_count         REAL,
            f_audit_score       REAL,
            f_moonbag_score     REAL,
            f_tokenscan_score   REAL,
            f_dev_status        TEXT,
            f_dev_hold_rate     REAL,
            f_rugcheck_score    REAL,

            -- entry market state (from position_features)
            liquidity_usd       REAL,
            holder_count        INTEGER,
            gmgn_total_fees_sol REAL,
            vol_mcap_ratio      REAL,
            mcap_tier           TEXT,
            gmgn_rug_ratio      REAL,
            gmgn_kol_count      INTEGER,
            gmgn_smart_count    INTEGER,
            gmgn_insider_rate   REAL,
            gmgn_bundler_rate   REAL,
            gmgn_sniper_rate    REAL,
            gmgn_burn_ratio     REAL,
            gmgn_renounced_mint INTEGER,
            gmgn_is_honeypot    INTEGER,
            gmgn_is_locked      INTEGER,

            -- token characteristics at entry
            is_graduated        INTEGER,
            token_age_at_entry_s INTEGER,
            regime_at_entry     TEXT,

            -- outcome metrics
            peak_pct            REAL,
            max_drawdown_pct    REAL,
            time_to_peak_ms     INTEGER,
            tick_count          INTEGER,
            exit_quality        TEXT,
            regret_score        REAL,
            infirmary_recovered_pct REAL,
            infirmary_status    TEXT,
            capture_ratio       REAL,
            missed_multiple     REAL,
            archetype           TEXT,

            -- execution
            execution_mode      TEXT,
            entry_signature     TEXT,
            exit_signature      TEXT
        );

        CREATE TABLE ticks (
            position_id         INTEGER NOT NULL,
            at_ms               INTEGER NOT NULL,
            hold_ms             INTEGER NOT NULL,
            mcap                REAL,
            price               REAL,
            pnl_percent         REAL,
            peak_pct            REAL,
            drawdown_pct        REAL,
            buys_5m             INTEGER,
            sells_5m            INTEGER,
            buy_vol_5m          REAL,
            sell_vol_5m         REAL,
            flow_ratio          REAL,
            smart_money         INTEGER,
            hot_level           REAL,
            exit_signal_state   TEXT,
            trail_pct           REAL,
            holder_count        INTEGER,
            kol_count           INTEGER,
            liquidity           REAL,
            sniper_wallets      INTEGER,
            whale_wallets       INTEGER,
            dev_status          TEXT,
            policy_signal       TEXT,
            PRIMARY KEY (position_id, at_ms)
        ) WITHOUT ROWID;

        CREATE TABLE post_mortem (
            position_id         INTEGER PRIMARY KEY,
            mint                TEXT NOT NULL,
            symbol              TEXT,
            entry_mcap          REAL,
            exit_mcap           REAL,
            exit_reason         TEXT,
            closed_at           TEXT,

            -- from post_exit_track
            post_peak_mcap      REAL,
            post_peak_at_ms     INTEGER,
            post_peak_mult      REAL,  -- post_peak / exit (how much left on table)
            post_peak_ts        TEXT,

            -- from trajectory_track
            all_time_peak_mcap  REAL,
            all_time_peak_at_ms INTEGER,
            all_time_peak_ts    TEXT,
            pre_exit_peak_mcap  REAL,
            pre_exit_peak_at_ms INTEGER,
            pre_exit_peak_ts    TEXT,
            dead                INTEGER,
            dead_confirmed_at   TEXT,

            -- trajectory enrichments
            first_entry_ms      INTEGER,
            last_entry_ms       INTEGER,
            reentry_count       INTEGER  -- denormalized: how many times we re-entered
        );

        CREATE TABLE screening (
            id                  INTEGER PRIMARY KEY,
            mint                TEXT NOT NULL,
            symbol              TEXT,
            source              TEXT,    -- 'regret_watch' | 'forsaken'

            -- filter details
            filter_reasons      TEXT,
            entry_mcap_usd      REAL,    -- mcap when rejected
            created_at          TEXT,
            resolved            INTEGER,

            -- outcome after rejection
            pump_pct_10m        REAL,
            pump_pct_60m        REAL,
            mcap_at_10m         REAL,
            mcap_at_60m         REAL,
            true_ath_mcap       REAL,
            ath_missed_multiple REAL,
            resolution          TEXT,    -- final verdict: 'pumped' | 'died' | 'unknown'
            post_call_missed_multiple REAL,

            -- enrichments
            is_graduated        INTEGER,
            kline_status        TEXT
        );

        CREATE TABLE simulations (
            id                  INTEGER PRIMARY KEY,
            position_id         INTEGER,
            mint                TEXT NOT NULL,
            symbol              TEXT,
            sim_type            TEXT NOT NULL,
                -- entry_shadow | moonbag | runner_mode | conviction | reentry

            -- sim-specific params (JSON)
            params_json         TEXT

            -- sim-specific results
            -- entry_shadow: would_block, block_leg, pnl_sol (of the blocked pos)
            -- moonbag: moonbag_frac, core_pnl_sol, moonbag_value_sol, vs_full_exit_sol, post_peak_mcap
            -- runner: armed_at_ms, armed_peak_pct, shadow_exit_mcap, shadow_exit_reason, shadow_realized_frac
            -- conviction: conviction_score, first_mcap, actual_entry_mcap, early_entry_mult
            -- reentry: exit_mcap, resignal_mcap, followup_mult
        );

        CREATE TABLE enrichment (
            mint                TEXT,
            source              TEXT,    -- 'tokenscan' | 'avescan'
            fetched_at          TEXT,

            -- common
            mcap                REAL,
            holder_count        INTEGER,
            liquidity           REAL,

            -- TokenScan-specific
            ath_usd             REAL,
            ath_drop_pct        REAL,
            vol_24h_usd         REAL,
            buys_1h             INTEGER,
            sells_1h            INTEGER,
            buy_sell_ratio      REAL,
            audit_score         TEXT,
            top10_holders_pct   REAL,
            bundled_pct         REAL,
            is_honeypot         INTEGER,
            has_socials         INTEGER,
            hot_rank            INTEGER,
            tier                TEXT,

            -- AveScan-specific
            symbol              TEXT,
            snipers             INTEGER,
            insiders            INTEGER,
            top10_pct           REAL,
            top20_pct           REAL,
            top30_pct           REAL,
            top40_pct           REAL,
            top50_pct           REAL,
            security_score      TEXT,
            risk_label          TEXT,
            no_mint             INTEGER,
            lp_burnt            INTEGER,
            change_15m          REAL,
            change_24h          REAL,

            PRIMARY KEY (mint, source)
        ) WITHOUT ROWID;

        CREATE TABLE learning (
            id                  INTEGER PRIMARY KEY,
            type                TEXT,    -- 'lesson' | 'hypothesis' | 'hypothesis_run'
            title               TEXT,
            body                TEXT,    -- lesson text or prediction
            author              TEXT,
            status              TEXT,    -- active | open | confirmed | falsified
            metric              REAL,   -- hypothesis metric or lesson score
            n_size              INTEGER,
            verdict             TEXT,
            evidence            TEXT,    -- JSON evidence or test SQL
            created_at          TEXT,
            notes               TEXT
        );
    """)
    con.commit()

def check_row_counts(msg, cur):
    print(f"  -> {msg}")

def export_positions(src_con, dst_con):
    """Consolidate dry_run_positions + position_features + retreat_log + tp_sl_rules"""
    print("Exporting positions...")
    src = src_con
    cur = src.execute("""
        SELECT
            p.*,
            pf.archetype, pf.mcap_tier, pf.liquidity_usd, pf.holder_count,
            pf.gmgn_total_fees_sol, pf.vol_mcap_ratio,
            pf.gmgn_rug_ratio, pf.gmgn_kol_count, pf.gmgn_smart_count,
            pf.gmgn_insider_rate, pf.gmgn_bundler_rate, pf.gmgn_sniper_rate,
            pf.gmgn_burn_ratio, pf.gmgn_renounced_mint, pf.gmgn_is_honeypot,
            pf.gmgn_is_locked, pf.gmgn_dev_hold_rate, pf.gmgn_top10_rate,
            pf.gmgn_serial_deployer,
            pf.hold_ms as pf_hold_ms, pf.peak_pct as pf_peak_pct,
            pf.time_to_peak_ms, pf.max_drawdown_pct, pf.tick_count,
            rl.exit_signal_state, rl.exit_signal_debounced, rl.dynamic_trail_pct,
            rl.flow_ratio as rl_flow_ratio, rl.smart_money as rl_smart_money,
            rl.smart_trend, rl.tokenscan_composite, rl.exit_tag,
            rl.entry_mcap as rl_entry_mcap, rl.exit_mcap as rl_exit_mcap,
            rl.exit_price as rl_exit_price, rl.hold_ms as rl_hold_ms,
            rl.exit_pnl_percent, rl.exit_pnl_sol
        FROM dry_run_positions p
        LEFT JOIN position_features pf ON pf.position_id = p.id
        LEFT JOIN (
            SELECT position_id, exit_signal_state, exit_signal_debounced,
                   dynamic_trail_pct, flow_ratio, smart_money, smart_trend,
                   tokenscan_composite, exit_tag, entry_mcap, exit_mcap,
                   exit_price, hold_ms, exit_pnl_percent, exit_pnl_sol
            FROM retreat_log
        ) rl ON rl.position_id = p.id
        ORDER BY p.id
    """)

    dst = dst_con
    insert = dst.executemany("""
        INSERT OR REPLACE INTO positions VALUES (
            :id, :mint, :symbol, :strategy_id, :route,
            :opened_at, :closed_at, :hold_ms,
            :size_sol, :calibrated_size_sol, :slippage_pct,
            :slippage_cost_sol, :gross_pnl_sol, :gross_pnl_percent,
            :net_pnl_sol, :pnl_sol, :pnl_percent,
            :entry_mcap, :entry_price, :exit_mcap, :exit_price,
            :high_water_mcap, :low_water_mcap,
            :exit_reason,
            :exit_signal_state, :exit_signal_debounced, :dynamic_trail_pct,
            :rl_flow_ratio, :rl_smart_money, :smart_trend,
            :tokenscan_composite, :exit_tag,
            :f_route, :f_hot_level, :f_smart_count, :f_obs_missed_mult,
            :f_holder_count, :f_fresh_rate, :f_gmgn_fees_sol, :f_kol_count,
            :f_audit_score, :f_moonbag_score, :f_tokenscan_score,
            :f_dev_status, :f_dev_hold_rate, :f_rugcheck_score,
            :liquidity_usd, :holder_count, :gmgn_total_fees_sol,
            :vol_mcap_ratio, :mcap_tier,
            :gmgn_rug_ratio, :gmgn_kol_count, :gmgn_smart_count,
            :gmgn_insider_rate, :gmgn_bundler_rate, :gmgn_sniper_rate,
            :gmgn_burn_ratio, :gmgn_renounced_mint, :gmgn_is_honeypot,
            :gmgn_is_locked,
            :is_graduated, :token_age_at_entry_s, :regime_at_entry,
            :pf_peak_pct, :max_drawdown_pct, :time_to_peak_ms,
            :tick_count, :exit_quality, :regret_score,
            :infirmary_recovered_pct, :infirmary_status,
            :exit_capture_ratio, :missed_multiple,
            :archetype,
            :execution_mode, :entry_signature, :exit_signature
        )
    """, ({
        'id': r['id'],
        'mint': r['mint'],
        'symbol': r['symbol'],
        'strategy_id': r['strategy_id'],
        'route': r['f_route'],
        'opened_at': ms2iso(r['opened_at_ms']),
        'closed_at': ms2iso(r['closed_at_ms']),
        'hold_ms': r['rl_hold_ms'] if r['rl_hold_ms'] else (
            r['closed_at_ms'] - r['opened_at_ms'] if r['closed_at_ms'] else None
        ),
        'size_sol': r['size_sol'],
        'calibrated_size_sol': r['calibrated_size_sol'],
        'slippage_pct': r['slippage_pct'],
        'slippage_cost_sol': r['slippage_cost_sol'],
        'gross_pnl_sol': r['gross_pnl_sol'],
        'gross_pnl_percent': r['gross_pnl_percent'],
        'net_pnl_sol': r['net_pnl_sol'],
        'pnl_sol': r['pnl_sol'],
        'pnl_percent': r['pnl_percent'],
        'entry_mcap': r['entry_mcap'],
        'entry_price': r['entry_price'],
        'exit_mcap': r['exit_mcap'] or r['rl_exit_mcap'],
        'exit_price': r['exit_price'] or r['rl_exit_price'],
        'high_water_mcap': r['high_water_mcap'],
        'low_water_mcap': r['low_water_mcap'],
        'exit_reason': r['exit_reason'],
        'exit_signal_state': r['exit_signal_state'],
        'exit_signal_debounced': r['exit_signal_debounced'],
        'dynamic_trail_pct': r['dynamic_trail_pct'],
        'rl_flow_ratio': r['rl_flow_ratio'],
        'rl_smart_money': r['rl_smart_money'],
        'smart_trend': r['smart_trend'],
        'tokenscan_composite': r['tokenscan_composite'],
        'exit_tag': r['exit_tag'],
        'f_route': r['f_route'],
        'f_hot_level': r['f_hot_level'],
        'f_smart_count': r['f_smart_count'],
        'f_obs_missed_mult': r['f_obs_missed_mult'],
        'f_holder_count': r['f_holder_count'],
        'f_fresh_rate': r['f_fresh_rate'],
        'f_gmgn_fees_sol': r['f_gmgn_fees_sol'],
        'f_kol_count': r['f_kol_count'],
        'f_audit_score': r['f_audit_score'],
        'f_moonbag_score': r['f_moonbag_score'],
        'f_tokenscan_score': r['f_tokenscan_score'],
        'f_dev_status': r['f_dev_status'],
        'f_dev_hold_rate': r['f_dev_hold_rate'],
        'f_rugcheck_score': r['f_rugcheck_score'],
        'liquidity_usd': r['liquidity_usd'],
        'holder_count': r['holder_count'],
        'gmgn_total_fees_sol': r['gmgn_total_fees_sol'],
        'vol_mcap_ratio': r['vol_mcap_ratio'],
        'mcap_tier': r['mcap_tier'],
        'gmgn_rug_ratio': r['gmgn_rug_ratio'],
        'gmgn_kol_count': r['gmgn_kol_count'],
        'gmgn_smart_count': r['gmgn_smart_count'],
        'gmgn_insider_rate': r['gmgn_insider_rate'],
        'gmgn_bundler_rate': r['gmgn_bundler_rate'],
        'gmgn_sniper_rate': r['gmgn_sniper_rate'],
        'gmgn_burn_ratio': r['gmgn_burn_ratio'],
        'gmgn_renounced_mint': r['gmgn_renounced_mint'],
        'gmgn_is_honeypot': r['gmgn_is_honeypot'],
        'gmgn_is_locked': r['gmgn_is_locked'],
        'is_graduated': r['is_graduated'],
        'token_age_at_entry_s': r['token_age_at_entry_s'],
        'regime_at_entry': r['regime_at_entry'],
        'pf_peak_pct': r['pf_peak_pct'],
        'max_drawdown_pct': r['max_drawdown_pct'],
        'time_to_peak_ms': r['time_to_peak_ms'],
        'tick_count': r['tick_count'],
        'exit_quality': r['exit_quality'],
        'regret_score': r['regret_score'],
        'infirmary_recovered_pct': r['infirmary_recovered_pct'],
        'infirmary_status': r['infirmary_status'],
        'exit_capture_ratio': r['exit_capture_ratio'],
        'missed_multiple': r['missed_multiple'],
        'archetype': r['archetype'],
        'execution_mode': r['execution_mode'],
        'entry_signature': r['entry_signature'],
        'exit_signature': r['exit_signature'],
    } for r in cur))
    n = dst.total_changes
    print(f"  -> {n} positions written")
    return n

def export_ticks(src_con, dst_con):
    print("Exporting ticks...")
    cur = src_con.execute("SELECT * FROM position_ticks ORDER BY position_id, at_ms")
    insert = dst_con.executemany("""
        INSERT OR REPLACE INTO ticks VALUES (
            :position_id, :at_ms, :hold_ms,
            :mcap, :price, :pnl_percent, :peak_pct, :drawdown_pct,
            :buys_5m, :sells_5m, :buy_vol_5m, :sell_vol_5m,
            :flow_ratio, :smart_money, :hot_level,
            :exit_signal_state, :trail_pct,
            :holder_count, :kol_count, :liquidity,
            :sniper_wallets, :whale_wallets,
            :dev_status, :policy_signal
        )
    """, (dict(r) for r in cur))
    n = dst_con.total_changes
    print(f"  -> {n} ticks written")
    return n

def export_post_mortem(src_con, dst_con):
    print("Exporting post-mortem...")
    # Merge post_exit_track + trajectory_track
    cur = src_con.execute("""
        SELECT
            p.position_id,
            p.mint,
            p.symbol,
            p.entry_mcap,
            p.exit_mcap,
            p.exit_reason,
            p.closed_at_ms,
            p.post_exit_peak_mcap,
            p.post_exit_peak_at_ms,
            p.post_exit_peak_mult,
            t.all_time_peak_mcap,
            t.all_time_peak_at_ms,
            t.pre_exit_peak_mcap,
            t.pre_exit_peak_at_ms,
            t.dead,
            t.dead_confirmed_at_ms,
            t.first_entry_ms,
            t.last_entry_ms
        FROM post_exit_track p
        LEFT JOIN trajectory_track t ON t.mint = p.mint
        WHERE p.position_id IS NOT NULL
        ORDER BY p.position_id
    """)
    rows = []
    reentry_counts = {}
    rc = src_con.execute("SELECT mint, COUNT(*) as cnt FROM trajectory_track WHERE last_entry_ms IS NOT NULL GROUP BY mint")
    for r in rc:
        reentry_counts[r['mint']] = r['cnt']

    for r in cur:
        rows.append({
            'position_id': r['position_id'] if r['position_id'] else 0,
            'mint': r['mint'],
            'symbol': r['symbol'],
            'entry_mcap': r['entry_mcap'],
            'exit_mcap': r['exit_mcap'],
            'exit_reason': r['exit_reason'],
            'closed_at': ms2iso(r['closed_at_ms']),
            'post_peak_mcap': r['post_exit_peak_mcap'],
            'post_peak_at_ms': r['post_exit_peak_at_ms'],
            'post_peak_mult': r['post_exit_peak_mult'],
            'post_peak_ts': ms2iso(r['post_exit_peak_at_ms']),
            'all_time_peak_mcap': r['all_time_peak_mcap'],
            'all_time_peak_at_ms': r['all_time_peak_at_ms'],
            'all_time_peak_ts': ms2iso(r['all_time_peak_at_ms']),
            'pre_exit_peak_mcap': r['pre_exit_peak_mcap'],
            'pre_exit_peak_at_ms': r['pre_exit_peak_at_ms'],
            'pre_exit_peak_ts': ms2iso(r['pre_exit_peak_at_ms']),
            'dead': r['dead'] or 0,
            'dead_confirmed_at': ms2iso(r['dead_confirmed_at_ms']),
            'first_entry_ms': r['first_entry_ms'],
            'last_entry_ms': r['last_entry_ms'],
            'reentry_count': reentry_counts.get(r['mint'], 0)
        })

    insert = dst_con.executemany("""
        INSERT OR REPLACE INTO post_mortem VALUES (
            :position_id, :mint, :symbol,
            :entry_mcap, :exit_mcap, :exit_reason, :closed_at,
            :post_peak_mcap, :post_peak_at_ms, :post_peak_mult, :post_peak_ts,
            :all_time_peak_mcap, :all_time_peak_at_ms, :all_time_peak_ts,
            :pre_exit_peak_mcap, :pre_exit_peak_at_ms, :pre_exit_peak_ts,
            :dead, :dead_confirmed_at,
            :first_entry_ms, :last_entry_ms, :reentry_count
        )
    """, rows)
    n = dst_con.total_changes
    print(f"  -> {n} post-mortem rows written")
    return n

def export_screening(src_con, dst_con):
    print("Exporting screening...")
    cur = src_con.execute("""
        SELECT *, 'regret_watch' as source FROM regret_watch ORDER BY id
    """)
    rows = [{
        'id': r['id'],
        'mint': r['mint'],
        'symbol': r['symbol'],
        'source': 'regret_watch',
        'filter_reasons': r['filter_reasons'],
        'entry_mcap_usd': r['entry_mcap_usd'],
        'created_at': ms2iso(r['created_at_ms']),
        'resolved': r['resolved'],
        'pump_pct_10m': r['pump_pct_10m'],
        'pump_pct_60m': r['pump_pct_60m'],
        'mcap_at_10m': r['mcap_at_10m'],
        'mcap_at_60m': r['mcap_at_60m'],
        'true_ath_mcap': r['true_ath_mcap'],
        'ath_missed_multiple': r['ath_missed_multiple'],
        'resolution': r['resolution'],
        'post_call_missed_multiple': r['post_call_missed_multiple'],
        'is_graduated': r['ath_is_graduated'],
        'kline_status': r['kline_status'],
    } for r in cur]

    insert = dst_con.executemany("""
        INSERT OR REPLACE INTO screening VALUES (
            :id, :mint, :symbol, :source,
            :filter_reasons, :entry_mcap_usd, :created_at, :resolved,
            :pump_pct_10m, :pump_pct_60m, :mcap_at_10m, :mcap_at_60m,
            :true_ath_mcap, :ath_missed_multiple, :resolution,
            :post_call_missed_multiple, :is_graduated, :kline_status
        )
    """, rows)
    n = dst_con.total_changes
    print(f"  -> {n} screening rows written")
    return n

def export_simulations(src_con, dst_con):
    """Unify 5 shadow tables into simulations table with JSON params+results."""
    print("Exporting simulations...")

    dst = dst_con
    start_rows = dst.total_changes

    # entry_shadow_block
    cur = src_con.execute("SELECT * FROM entry_shadow_block WHERE resolved=1")
    for r in cur:
        dst.execute("""
            INSERT INTO simulations (position_id, mint, symbol, sim_type, params_json)
            VALUES (?, ?, ?, 'entry_shadow', ?)
        """, (
            r['position_id'], r['mint'], r['symbol'],
            json.dumps({
                'num_kols': r['num_kols'],
                'top_holders_pct': r['top_holders_pct'],
                'kols_null': r['kols_null'],
                'top_null': r['top_null'],
                'would_block': r['would_block'],
                'block_leg': r['block_leg'],
                'pnl_sol': r['pnl_sol'],
            })
        ))

    # moonbag_shadow
    cur = src_con.execute("SELECT * FROM moonbag_shadow WHERE post_peak_mcap IS NOT NULL")
    for r in cur:
        dst.execute("""
            INSERT INTO simulations (position_id, mint, symbol, sim_type, params_json)
            VALUES (?, ?, ?, 'moonbag', ?)
        """, (
            r['position_id'], r['mint'], r['symbol'],
            json.dumps({
                'moonbag_frac': r['moonbag_frac'],
                'core_pnl_sol': r['core_pnl_sol'],
                'moonbag_value_sol': r['moonbag_value_sol'],
                'vs_full_exit_sol': r['vs_full_exit_sol'],
                'post_peak_mcap': r['post_peak_mcap'],
                'size_sol': r['size_sol'],
            })
        ))

    # runner_mode_shadow
    cur = src_con.execute("SELECT * FROM runner_mode_shadow WHERE resolved=1")
    for r in cur:
        dst.execute("""
            INSERT INTO simulations (position_id, mint, symbol, sim_type, params_json)
            VALUES (?, ?, ?, 'runner_mode', ?)
        """, (
            r['position_id'], r['mint'], r['symbol'],
            json.dumps({
                'armed_at_ms': r['armed_at_ms'],
                'armed_peak_pct': r['armed_peak_pct'],
                'sold_50_mcap': r['sold_50_mcap'],
                'sold_25_mcap': r['sold_25_mcap'],
                'shadow_exit_mcap': r['shadow_exit_mcap'],
                'shadow_exit_reason': r['shadow_exit_reason'],
                'shadow_realized_frac': r['shadow_realized_frac'],
            })
        ))

    # conviction_entry_shadow
    cur = src_con.execute("SELECT * FROM conviction_entry_shadow WHERE actual_entered=1")
    for r in cur:
        dst.execute("""
            INSERT INTO simulations (position_id, mint, symbol, sim_type, params_json)
            VALUES (NULL, ?, ?, 'conviction', ?)
        """, (
            r['mint'], r['symbol'],
            json.dumps({
                'first_signal_ms': r['first_signal_ms'],
                'first_mcap': r['first_mcap'],
                'signal_count': r['signal_count'],
                'conviction_score': r['conviction_score'],
                'actual_entry_mcap': r['actual_entry_mcap'],
                'first_signal_peak_mcap': r['first_signal_peak_mcap'],
                'early_entry_mult': r['early_entry_mult'],
                'mcap_creep_pct': r['mcap_creep_pct'],
            })
        ))

    # reentry_shadow
    cur = src_con.execute("SELECT * FROM reentry_shadow WHERE followup_mult IS NOT NULL")
    for r in cur:
        dst.execute("""
            INSERT INTO simulations (position_id, mint, symbol, sim_type, params_json)
            VALUES (NULL, ?, ?, 'reentry', ?)
        """, (
            r['mint'], r['symbol'],
            json.dumps({
                'exit_mcap': r['exit_mcap'],
                'exit_reason': r['exit_reason'],
                'resignal_mcap': r['resignal_mcap'],
                'mcap_over_exit_pct': r['mcap_over_exit_pct'],
                'followup_peak_mcap': r['followup_peak_mcap'],
                'followup_mult': r['followup_mult'],
            })
        ))

    n = dst.total_changes - start_rows
    print(f"  -> {n} simulation rows written")
    return n

def export_enrichment(src_con, dst_con):
    """Unify tokenscan_enrichment + avescan_camus into enrichment table."""
    print("Exporting enrichment...")

    dst = dst_con
    start_rows = dst.total_changes

    # tokenscan
    cur = src_con.execute("SELECT * FROM tokenscan_enrichment")
    for r in cur:
        dst.execute("""
            INSERT OR REPLACE INTO enrichment VALUES (
                ?, 'tokenscan', ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?,
                NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
            )
        """, (
            r['mint'],
            ms2iso(r['fetched_at_ms']),
            r['mc_usd'],
            r['holders'],
            r['liq_usd'],
            r['ath_usd'],
            r['ath_drop_pct'],
            r['vol_24h_usd'],
            r['buys_1h'],
            r['sells_1h'],
            r['buy_sell_ratio'],
            r['audit_score'],
            r['top10_holders_pct'],
            r['bundled_pct'],
            r['is_honeypot'],
            r['has_socials'],
            r['hot_rank'],
            r['tier'],
            # AveScan fields — all NULL
        ))

    # avescan_camus
    cur = src_con.execute("SELECT * FROM avescan_camus")
    for r in cur:
        dst.execute("""
            INSERT OR REPLACE INTO enrichment VALUES (
                ?, 'avescan', ?,
                ?, ?, NULL,
                NULL, NULL,
                NULL, NULL, NULL, NULL,
                NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            r['mint'],
            ms2iso(r['enriched_at_ms']),
            r['camus_entry_mcap'],
            r['holder_total'],
            r['symbol'],
            r['snipers'],
            r['insiders'],
            r['top10_pct'],
            r['top20_pct'],
            r['top30_pct'],
            r['top40_pct'],
            r['top50_pct'],
            r['security_score'],
            r['risk_label'],
            r['no_mint'],
            r['lp_burnt'],
            r['change_15m'],
            r['change_24h'],
        ))

    n = dst.total_changes - start_rows
    print(f"  -> {n} enrichment rows written")
    return n

def export_learning(src_con, dst_con):
    print("Exporting learning...")

    dst = dst_con
    start_rows = dst.total_changes

    # lessons
    cur = src_con.execute("""
        SELECT 'lesson' as type, NULL as title, lesson as body,
               NULL as author, status, 0 as metric, 0 as n_size,
               NULL as verdict, evidence_json, created_at_ms, NULL as notes
        FROM learning_lessons ORDER BY id
    """)
    for r in cur:
        dst.execute("""
            INSERT INTO learning (type, title, body, author, status, metric, n_size, verdict, evidence, created_at, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            r['type'], r['title'], r['body'], r['author'], r['status'],
            r['metric'], r['n_size'], r['verdict'],
            r['evidence_json'],
            ms2iso(r['created_at_ms']),
            r['notes']
        ))

    # hypotheses
    cur = src_con.execute("""
        SELECT 'hypothesis' as type, title, mechanism as body,
               author, status, last_metric as metric, last_n as n_size,
               last_verdict as verdict, test_sql as evidence,
               created_at_ms, notes || COALESCE('; origin: ' || origin, '') as notes
        FROM hypotheses ORDER BY id
    """)
    for r in cur:
        dst.execute("""
            INSERT INTO learning (type, title, body, author, status, metric, n_size, verdict, evidence, created_at, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            r['type'], r['title'], r['body'], r['author'], r['status'],
            r['metric'], r['n_size'], r['verdict'],
            r['evidence'],
            ms2iso(r['created_at_ms']),
            r['notes']
        ))

    # hypothesis_runs
    cur = src_con.execute("""
        SELECT 'hypothesis_run' as type, h.title as title,
               h.title || ' run' as body, h.author as author,
               hr.verdict as status, hr.metric, h.min_n as n_size,
               hr.verdict, hr.detail as evidence,
               hr.at_ms as created_at_ms, NULL as notes
        FROM hypothesis_runs hr
        JOIN hypotheses h ON h.id = hr.hypothesis_id
        ORDER BY hr.id
    """)
    for r in cur:
        dst.execute("""
            INSERT INTO learning (type, title, body, author, status, metric, n_size, verdict, evidence, created_at, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            r['type'], r['title'], r['body'], r['author'], r['status'],
            r['metric'], r['n_size'], r['verdict'],
            r['evidence'],
            ms2iso(r['created_at_ms']),
            r['notes']
        ))

    n = dst.total_changes - start_rows
    print(f"  -> {n} learning rows written")
    return n


def main():
    os.makedirs("data", exist_ok=True)

    print("=== Camus Warehouse Export ===")
    print(f"Source: {SRC}")
    print(f"Dest:   {DST}")
    print()

    srcc = connect(SRC)
    dstc = sqlite3.connect(DST)

    print("Creating schema...")
    create_dst(dstc)

    print("\nExporting tables:")
    tot = 0
    tot += export_positions(srcc, dstc)
    tot += export_ticks(srcc, dstc)
    tot += export_post_mortem(srcc, dstc)
    tot += export_screening(srcc, dstc)
    tot += export_simulations(srcc, dstc)
    tot += export_enrichment(srcc, dstc)
    tot += export_learning(srcc, dstc)

    print(f"\n=== Done. {tot} total rows written ===")

    # VACUUM to reclaim space
    dstc.commit()  # commit before VACUUM
    print("Vacuuming...")
    dstc.execute("VACUUM")
    dstc.close()
    srcc.close()

    # Show final size
    sz = os.path.getsize(DST)
    print(f"Warehouse size: {sz/1048576:.1f} MB")

if __name__ == "__main__":
    main()
