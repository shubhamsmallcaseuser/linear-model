"""
motif_engine.py — Motif matching exactly as notebook cells 3-7.

Notebook pipeline:
  Cell 3:  rvDf = (returns**2).rename('RV')
  Cell 4:  mk.Match(rvDf, rebalDate, windowSize=45, threshold=0.50)
           → top5 per date, append to top_regimes
  Cell 6:  forward 1M stats per analogue (Vol_1M, MeanRet, etc.)
  Cell 7:  winsorize dp (upper 1% only)
"""

import numpy as np
import pandas as pd
from scipy.stats import skew, kurtosis
from typing import List


class MotifEngine:
    def __init__(self, config):
        self.cfg = config

    def build_rv_series(self, price_series: pd.Series) -> pd.DataFrame:
        """Cell 3: squared daily returns → RV DataFrame."""
        returns = price_series.pct_change().dropna()
        rv = (returns ** 2).rename("RV").to_frame()
        return rv

    def run_matching(
        self,
        rv_df: pd.DataFrame,
        price_series: pd.Series,
        rebal_dates: List[pd.Timestamp],
    ) -> pd.DataFrame:
        """
        Cell 4: mk.Match with threshold=0.50, top 5 per date.
        Cell 6: attach forward 1M stats.
        Cell 7: winsorize dp.
        """
        import Python_Scripts.mass as mk
        from scipy.stats.mstats import winsorize as scipy_winsorize

        top_regimes = []
        skipped = 0

        for rebal_date in rebal_dates:
            try:
                sim = mk.Match(
                    rv_df,
                    rebal_date,
                    windowSize=self.cfg.motif_window,    # 45
                    threshold=self.cfg.motif_threshold,  # 0.50
                )
                reg = sim.getRegime()
            except (IndexError, Exception):
                skipped += 1
                continue

            if reg.empty:
                skipped += 1
                continue

            top5 = reg.head(self.cfg.motif_top_k).copy()  # top 5
            top5["RebalDate"] = rebal_date
            top_regimes.append(top5)

        print(f"[MotifEngine] Processed {len(rebal_dates)} | "
              f"Matched: {len(rebal_dates)-skipped} | Skipped: {skipped}")

        if not top_regimes:
            raise RuntimeError("No matching regimes found. Try adjusting motif_threshold.")

        df = pd.concat(top_regimes, ignore_index=True)
        df["start"] = pd.to_datetime(df["start"])
        df["end"] = pd.to_datetime(df["end"])

        # Cell 6: forward 1M stats
        df = self._attach_forward_stats(df, price_series)

        # Cell 7: winsorize dp — upper 1% only, exactly as notebook
        if "dp" in df.columns:
            non_na = df["dp"].dropna()
            w = scipy_winsorize(non_na, limits=[0, 0.01])
            df.loc[non_na.index, "dp"] = w

        print(f"[MotifEngine] Total motif rows: {len(df)}")
        return df

    def _attach_forward_stats(
        self, df: pd.DataFrame, price_series: pd.Series
    ) -> pd.DataFrame:
        """Cell 6: compute 1M forward stats for each analogue end date."""
        prices = price_series.to_frame("price")
        prices.index = pd.to_datetime(prices.index)

        for col in ["MeanRet_1M", "Vol_1M", "RealizedVol_1M", "Skew_1M", "Kurt_1M"]:
            df[col] = np.nan

        for idx, row in df.iterrows():
            end_date = row["end"]
            next_month_end = end_date + pd.DateOffset(months=1)

            mask = (prices.index > end_date) & (prices.index <= next_month_end)
            fwd_prices = prices.loc[mask, "price"]

            if len(fwd_prices) < 5:
                continue

            rets = fwd_prices.pct_change().dropna()
            df.at[idx, "MeanRet_1M"] = rets.mean()
            df.at[idx, "Vol_1M"] = rets.std()
            df.at[idx, "RealizedVol_1M"] = np.sum(rets ** 2)
            df.at[idx, "Skew_1M"] = skew(rets)
            df.at[idx, "Kurt_1M"] = kurtosis(rets, fisher=True)

        return df
