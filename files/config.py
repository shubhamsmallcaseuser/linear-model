"""
config.py — All parameters for the pipeline. Edit this file only.
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class PipelineConfig:
    # ── Data paths ────────────────────────────────────────────────────────
    price_file: str          = r"D:\Linear Model\data\Universe\INDTradingDays.xlsx"
    price_sheet: str         = "Close"
    trading_days_file: str   = r"D:\Linear Model\data\Universe\TradingDays.xlsx"
    trading_days_sheet: str  = "Sheet1"
    rebal_dates_file: str    = r"D:\Linear Model\data\RSI\Final\NSEI\W_allRebal.xlsx"

    # ── Universe ──────────────────────────────────────────────────────────
    tickers: List[str] = field(default_factory=lambda: [
        ".NSEI",
        # Add more tickers here — they must exist as columns in price_file
        # e.g. ".NIFTY100", ".BSESN", "RELIANCE.NS"
    ])

    # ── Date range ────────────────────────────────────────────────────────
    start_date: str   = "2004-01-01"   # pipeline start (rebal dates filtered from here)
    signal_start: str = "2020-01-01"   # export start (rows before this are dropped in output)

    # ── Motif matching (notebook: window=45, threshold=0.50, top_k=5) ────
    motif_window: int      = 45
    motif_top_k: int       = 5
    motif_threshold: float = 0.50

    # ── Output ────────────────────────────────────────────────────────────
    output_dir: str       = "output"
    output_excel: str     = "smoothed_signal_all_tickers.xlsx"
    ranking_excel: str    = "volatility_ranking.xlsx"
    plot_charts: bool     = True
