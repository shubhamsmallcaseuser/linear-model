"""
main.py — Entry point. Runs the exact notebook pipeline for each ticker,
          ranks the universe, and saves outputs.

Usage:
    python main.py
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

from config import PipelineConfig
from data_loader import DataLoader
from motif_engine import MotifEngine
from vol_aggregator import VolAggregator
from universe_ranker import UniverseRanker
from output_writer import OutputWriter
import charting


def run_ticker(
    ticker: str,
    price_df: pd.DataFrame,
    rebal_dates: list,
    cfg: PipelineConfig,
) -> pd.DataFrame:
    """
    Full pipeline for one ticker → returns first_of_month_df.

    Parameters
    ----------
    price_df    : full price DataFrame (all tickers, used for rvDf and closeMergedDf)
    rebal_dates : all rebal dates
    """
    print(f"\n{'='*60}")
    print(f"  Processing: {ticker}")
    print(f"{'='*60}")

    # Extract single-ticker price series
    price_series = price_df[ticker].dropna()
    # Keep as DataFrame for realized_vol function (needs iloc[:,0])
    price_single_df = price_series.to_frame()

    engine     = MotifEngine(cfg)
    aggregator = VolAggregator(cfg)

    # Step 1: Build RV series
    rv_df = engine.build_rv_series(price_series)

    # Step 2: Motif matching + forward stats + dp winsorize
    top_regimes_df = engine.run_matching(rv_df, price_series, rebal_dates)

    # Step 3: Full aggregation pipeline → first_of_month_df
    first_of_month_df = aggregator.run(
        top_regimes_df=top_regimes_df,
        price_df=price_single_df,
        rebal_dates_file=cfg.rebal_dates_file,   # pass file path, not list
    )

    first_of_month_df["Ticker"] = ticker

    # Latest signal for logging
    latest = first_of_month_df["Vol_Regime_Smooth"].iloc[-1]
    print(f"[main] {ticker} — monthly rows: {len(first_of_month_df)}  |  "
          f"latest Vol_Regime_Smooth: {latest:.4f}")

    return first_of_month_df


def main():
    cfg = PipelineConfig()
    os.makedirs(cfg.output_dir, exist_ok=True)

    # ── 1. Load data ──────────────────────────────────────────────────────
    loader = DataLoader(cfg)
    price_df, rebal_dates = loader.load_all()

    # ── 2. Run pipeline per ticker ────────────────────────────────────────
    all_signals: dict = {}

    for ticker in cfg.tickers:
        if ticker not in price_df.columns:
            print(f"[main] Skipping {ticker} — not found in price data.")
            continue
        try:
            sig_df = run_ticker(ticker, price_df, rebal_dates, cfg)
            all_signals[ticker] = sig_df

            if cfg.plot_charts:
                charting.plot_regime_signal(
                    sig_df[sig_df["RebalDate"] >= cfg.signal_start],
                    ticker=ticker,
                    output_path=os.path.join(cfg.output_dir, f"{ticker}_regime_signal.png"),
                )

        except Exception as exc:
            print(f"[main] ERROR on {ticker}: {exc}")
            import traceback; traceback.print_exc()

    if not all_signals:
        print("[main] No tickers processed. Exiting.")
        return

    # ── 3. Cross-sectional ranking ────────────────────────────────────────
    ranker     = UniverseRanker(cfg)
    ranking_df = ranker.build_ranking(all_signals)
    picks_df   = ranker.get_least_volatile(ranking_df, top_n=5, signal_threshold=0.40)

    print("\n" + "="*60)
    print("  VOLATILITY RANKING (least → most volatile)")
    print("="*60)
    print(ranking_df[["Rank", "Ticker", "LatestSignal",
                       "AvgSignal_6M", "PctTimeHighVol_1Y"]].to_string(index=False))
    print("\n  LEAST VOLATILE PICKS")
    print("-"*40)
    print(picks_df[["Rank", "Ticker", "LatestSignal"]].to_string(index=False))

    # ── 4. Charts ─────────────────────────────────────────────────────────
    if cfg.plot_charts and len(all_signals) > 1:
        charting.plot_universe_ranking(
            ranking_df,
            output_path=os.path.join(cfg.output_dir, "universe_ranking.png"),
        )
        charting.plot_cross_ticker_heatmap(
            all_signals,
            output_path=os.path.join(cfg.output_dir, "cross_ticker_heatmap.png"),
        )

    # ── 5. Save outputs ───────────────────────────────────────────────────
    writer = OutputWriter(cfg)
    writer.save_signals(all_signals, signal_start=cfg.signal_start)
    writer.save_ranking(ranking_df, picks_df)

    panel = ranker.build_timeseries_panel(all_signals)
    writer.save_panel(panel)

    print("\n[main] Pipeline complete.")

    # ── 6. Validation (only when single ticker) ───────────────────────────
    if len(all_signals) == 1:
        _run_validation(all_signals, cfg)


def _run_validation(all_signals: dict, cfg: PipelineConfig):
    """Compare output to original smoothed_signal.xlsx if it exists."""
    orig_path = os.path.join(cfg.output_dir, "..", "smoothed_signal.xlsx")
    if not os.path.exists(orig_path):
        return

    ticker = list(all_signals.keys())[0]
    sheet  = ticker.replace(".", "_")[:31]
    new_path = os.path.join(cfg.output_dir, cfg.output_excel)

    try:
        orig = pd.read_excel(orig_path)
        orig["RebalDate"] = pd.to_datetime(orig["RebalDate"])

        new = pd.read_excel(new_path, sheet_name=sheet)
        new["RebalDate"] = pd.to_datetime(new["RebalDate"])

        merged = orig.merge(new, on="RebalDate", suffixes=("_orig", "_new"))

        print(f"\n{'='*60}")
        print("  VALIDATION vs original smoothed_signal.xlsx")
        print(f"{'='*60}")
        print(f"  Orig rows: {len(orig)} | New rows: {len(new)} | Matched: {len(merged)}")

        for col in ["Vol_Regime_Smooth", "Vol_Regime_Monthly",
                    "WgtVol_1M", "CalibVol_Scaled"]:
            oc, nc = f"{col}_orig", f"{col}_new"
            if oc in merged and nc in merged:
                diff = (merged[oc] - merged[nc]).abs()
                print(f"\n  {col}:")
                print(f"    Max diff:  {diff.max():.8f}")
                print(f"    Mean diff: {diff.mean():.8f}")

        if "Vol_Regime_Smooth_orig" in merged:
            print("\n  First 10 rows — Vol_Regime_Smooth:")
            print(merged[["RebalDate",
                           "Vol_Regime_Smooth_orig",
                           "Vol_Regime_Smooth_new"]].head(10).to_string(index=False))
    except Exception as e:
        print(f"[validation] Could not run: {e}")


if __name__ == "__main__":
    main()
