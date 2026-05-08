"""
universe_ranker.py — Aggregates per-ticker signals and ranks the universe
                     from least to most volatile.
"""

import numpy as np
import pandas as pd
from typing import Dict, List


class UniverseRanker:
    """
    Given a dict of {ticker → signal_df}, computes a cross-sectional
    volatility ranking and produces pick lists.
    """

    def __init__(self, config):
        self.cfg = config

    # ── Public interface ─────────────────────────────────────────────────────

    def build_ranking(self, all_signals: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Build a summary ranking DataFrame for the latest available date.

        Columns returned
        ----------------
        Ticker, LatestSignal, AvgSignal_3M, AvgSignal_6M,
        AvgSignal_1Y, PctTimeHighVol, Rank (1 = least volatile)
        """
        rows = []
        for ticker, df in all_signals.items():
            if df.empty:
                continue
            df = df.sort_values("RebalDate")
            signal = df.set_index("RebalDate")["Vol_Regime_Smooth"].dropna()

            if signal.empty:
                continue

            latest = signal.iloc[-1]
            latest_date = signal.index[-1]

            # Rolling lookback averages (calendar-based slicing)
            avg_3m = signal.loc[signal.index >= latest_date - pd.DateOffset(months=3)].mean()
            avg_6m = signal.loc[signal.index >= latest_date - pd.DateOffset(months=6)].mean()
            avg_1y = signal.loc[signal.index >= latest_date - pd.DateOffset(months=12)].mean()

            # % of weeks where signal > 0.5 (high-vol regime) over past year
            past_1y = signal.loc[signal.index >= latest_date - pd.DateOffset(months=12)]
            pct_high_vol = float((past_1y > 0.5).mean()) if len(past_1y) > 0 else np.nan

            rows.append({
                "Ticker": ticker,
                "LatestDate": latest_date,
                "LatestSignal": latest,
                "AvgSignal_3M": avg_3m,
                "AvgSignal_6M": avg_6m,
                "AvgSignal_1Y": avg_1y,
                "PctTimeHighVol_1Y": pct_high_vol,
            })

        ranking = pd.DataFrame(rows)
        if ranking.empty:
            return ranking

        # Rank: lowest LatestSignal = rank 1 (least volatile)
        ranking["Rank"] = ranking["LatestSignal"].rank(ascending=True).astype(int)
        ranking = ranking.sort_values("Rank").reset_index(drop=True)

        return ranking

    def get_least_volatile(
        self,
        ranking: pd.DataFrame,
        top_n: int = 5,
        signal_threshold: float = 0.40,
    ) -> pd.DataFrame:
        """
        Return the top_n least volatile tickers where the latest signal
        is below signal_threshold.

        Parameters
        ----------
        ranking          : output of build_ranking
        top_n            : how many tickers to return
        signal_threshold : only include tickers with LatestSignal < this value

        Returns
        -------
        picks : DataFrame of selected tickers, sorted by Rank
        """
        picks = ranking[ranking["LatestSignal"] <= signal_threshold].head(top_n)

        if picks.empty:
            print(
                f"[UniverseRanker] No ticker has signal ≤ {signal_threshold}. "
                "Returning the top-{top_n} lowest regardless."
            )
            picks = ranking.head(top_n)

        return picks.reset_index(drop=True)

    def build_timeseries_panel(
        self, all_signals: Dict[str, pd.DataFrame]
    ) -> pd.DataFrame:
        """
        Wide DataFrame: index = RebalDate, columns = ticker signals.
        Useful for heatmaps and correlation analysis.
        """
        frames = {}
        for ticker, df in all_signals.items():
            if not df.empty:
                s = df.set_index("RebalDate")["Vol_Regime_Smooth"]
                frames[ticker] = s

        panel = pd.DataFrame(frames).sort_index()
        return panel

    def regime_correlation(self, panel: pd.DataFrame) -> pd.DataFrame:
        """Pairwise Pearson correlation of vol-regime signals across tickers."""
        return panel.corr()
