"""
vol_aggregator.py — Exact replication of notebook cells 9–86.

Notebook pipeline order:
  Cell  9:  inverse-distance weighted aggregation → rebal_weighted_stats
  Cell 10:  winsorize WgtVol_1M, WgtRealizedVol_1M
  Cell 14:  observed_vol per date → nw_forecast_df["Observed_Vol_1M"] (winsorized)
  Cell 28:  rebal_weighted_stats["Observed_Vol_1M"] = nw_forecast_df["Observed_Vol_1M"]
            → dropna
  Cell 33:  quantile bucketing on observed_vols_df (ALL weekly rebal dates)
            using past-only QuantileTransformer
  Cell 61:  bucket_means (median of Observed_VolBucket per VolBucket)
  Cell 62:  global exp fit: VolBucket → Observed_VolBucket (STATIC, not rolling)
  Cell 63:  Calibrated_VolBucket = exp_func(VolBucket, a, b)
  Cell 66:  ROLLING exp fit (window=156 weekly): refit a,b per date
            Calibrated_VolBucket overwritten with rolling version
  Cell 68:  CalibVol_Scaled = rolling min-max (window=156, min_periods=52)
  Cell 76:  mask = rebal_weighted_stats.dropna()
  Cell 78:  Vol_Regime_Monthly = CalibVol_Scaled.rolling(4, min_periods=2).mean()
            applied to mask (already weekly rows, no month sampling yet)
  Cell 80:  Vol_Regime_Smooth = CalibVol_Scaled.ewm(alpha=0.15).mean()
            (lambda=0.85, alpha=1-lambda=0.15)  applied to mask
  Cell 83:  first_of_month_df = first rebal date per calendar month from mask
  Cell 86:  export rows >= 2020-01-01
"""

import warnings
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from scipy.stats.mstats import winsorize as scipy_winsorize
from sklearn.preprocessing import QuantileTransformer


def _winsorize_series(series: pd.Series, lower: float = 0.01, upper: float = 0.01) -> pd.Series:
    """Winsorize preserving NaN — exactly as notebook helper."""
    if series.isnull().all():
        return series
    s = series.copy()
    non_na = s.dropna()
    w = scipy_winsorize(non_na, limits=[lower, upper])
    s.loc[non_na.index] = w
    return s


def _exp_func(x, a, b):
    return a * np.exp(b * x)


def _realized_vol_1m(price_df: pd.DataFrame, date: pd.Timestamp) -> float:
    """Notebook cell 14: std of daily returns in 1M window after date."""
    end = date + pd.DateOffset(months=1)
    mask = (price_df.index > date) & (price_df.index <= end)
    prices = price_df.loc[mask].iloc[:, 0]
    if len(prices) < 2:
        return np.nan
    return prices.pct_change().dropna().std()


class VolAggregator:
    """
    Runs the full notebook pipeline from top_regimes_df → smoothed monthly signal.
    """

    def __init__(self, config):
        self.cfg = config

    def run(
        self,
        top_regimes_df: pd.DataFrame,
        price_df: pd.DataFrame,          # full price DataFrame (from 1995)
        rebal_dates_file: str,           # path to W_allRebal.xlsx (for pool building)
    ) -> pd.DataFrame:
        """
        Returns first_of_month_df — the final monthly signal DataFrame.
        All rows included (not filtered by start date — do that in main.py).
        """

        # ── Cell 9: inverse-distance weighted aggregation ─────────────────
        rebal_weighted_stats = self._weighted_aggregation(top_regimes_df)

        # ── Cell 10: winsorize WgtVol_1M, WgtRealizedVol_1M ──────────────
        for col in ["WgtVol_1M", "WgtRealizedVol_1M"]:
            if col in rebal_weighted_stats.columns:
                rebal_weighted_stats[col] = _winsorize_series(
                    rebal_weighted_stats[col], lower=0.01, upper=0.01)

        # ── Cells 12-14: nw_forecast_df with Observed_Vol_1M ─────────────
        # (notebook computes NW forecasts but only Observed_Vol_1M is used downstream)
        nw_forecast_df = self._build_nw_forecast(top_regimes_df, price_df)

        # ── Cell 28: attach Observed_Vol_1M to rebal_weighted_stats ───────
        rebal_weighted_stats = rebal_weighted_stats.copy()
        rebal_weighted_stats["RebalDate"] = pd.to_datetime(rebal_weighted_stats["RebalDate"])
        nw_forecast_df["RebalDate"] = pd.to_datetime(nw_forecast_df["RebalDate"])

        rebal_weighted_stats["Observed_Vol_1M"] = (
            nw_forecast_df.set_index("RebalDate")["Observed_Vol_1M"]
            .reindex(rebal_weighted_stats["RebalDate"].values)
            .values
        )
        rebal_weighted_stats = rebal_weighted_stats.dropna()

        # ── Cells 22-26: observed_vols_df from ALL rebal dates (back to 1995) ──
        observed_vols_df = self._build_observed_vols_pool(price_df, rebal_dates_file)

        # ── Cell 33: quantile bucketing (past-only) ───────────────────────
        rebal_weighted_stats = self._quantile_bucketing(
            rebal_weighted_stats, observed_vols_df, nw_forecast_df)

        # ── Cells 61-66: rolling exp calibration (window=156 weekly) ──────
        rebal_weighted_stats = self._rolling_exp_calibration(rebal_weighted_stats)

        # ── Cell 68: rolling min-max scaling (window=156, min_periods=52) ─
        rebal_weighted_stats = self._rolling_minmax_scale(rebal_weighted_stats)

        # ── Cell 76: mask = dropna ────────────────────────────────────────
        mask = rebal_weighted_stats.dropna().copy()

        # ── Cell 78: Vol_Regime_Monthly (rolling 4, min_periods=2) ────────
        mask["Vol_Regime_Monthly"] = (
            mask["CalibVol_Scaled"]
            .rolling(window=4, min_periods=2)
            .mean()
        )

        # ── Cell 80: Vol_Regime_Smooth (EWMA lambda=0.85) ─────────────────
        mask["Vol_Regime_Smooth"] = (
            mask["CalibVol_Scaled"]
            .ewm(alpha=(1 - 0.85), adjust=False)
            .mean()
        )

        # ── Cell 83: first rebal date of each calendar month ──────────────
        mask["RebalDate"] = pd.to_datetime(mask["RebalDate"])
        first_of_month_df = (
            mask.loc[
                mask.groupby(mask["RebalDate"].dt.to_period("M"))["RebalDate"].idxmin()
            ]
            .reset_index(drop=True)
        )

        return first_of_month_df

    # ── Cell 9: Weighted aggregation ──────────────────────────────────────

    def _weighted_aggregation(self, df: pd.DataFrame) -> pd.DataFrame:
        def _wavg(group: pd.DataFrame, value_col: str) -> float:
            sub = group[[value_col, "dp"]].dropna()
            if sub.empty:
                return np.nan
            inv_w = 1.0 / sub["dp"]
            weights = inv_w / inv_w.sum()
            return float(np.sum(sub[value_col] * weights))

        records = []
        for rebal, group in df.groupby("RebalDate"):
            records.append({
                "RebalDate": rebal,
                "WgtVol_1M":         _wavg(group, "Vol_1M"),
                "WgtMeanRet_1M":     _wavg(group, "MeanRet_1M"),
                "WgtRealizedVol_1M": _wavg(group, "RealizedVol_1M"),
                "WgtSkew_1M":        _wavg(group, "Skew_1M"),
                "WgtKurt_1M":        _wavg(group, "Kurt_1M"),
            })

        result = pd.DataFrame(records).sort_values("RebalDate").reset_index(drop=True)
        return result

    # ── Cells 12-14: NW forecast + Observed_Vol_1M ────────────────────────

    def _build_nw_forecast(
        self,
        top_regimes_df: pd.DataFrame,
        price_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Build nw_forecast_df exactly as notebook cells 12-14."""

        # Cell 12: NW forecast per rebal date
        def _nw(group):
            sub = group[["Vol_1M", "dp"]].dropna()
            if sub.empty:
                return np.nan
            mean_dp = sub["dp"].mean()
            eta = mean_dp * 0.2
            if eta <= 0:
                eta = 1e-5
            weights = np.exp(-(sub["dp"] ** 2) / (2 * eta ** 2))
            weights /= weights.sum()
            return float(np.sum(weights * sub["Vol_1M"]))

        nw_records = []
        for rebal, group in top_regimes_df.groupby("RebalDate"):
            nw_records.append({"RebalDate": rebal, "NW_Vol_1M": _nw(group)})

        nw_df = pd.DataFrame(nw_records).sort_values("RebalDate").reset_index(drop=True)
        nw_df["NW_Vol_1M"] = _winsorize_series(nw_df["NW_Vol_1M"], lower=0.01, upper=0.01)

        # Cell 14: observed vol per rebal date
        nw_df["RebalDate"] = pd.to_datetime(nw_df["RebalDate"])
        obs_vols = [_realized_vol_1m(price_df, d) for d in nw_df["RebalDate"]]
        nw_df["Observed_Vol_1M"] = obs_vols
        nw_df["Observed_Vol_1M"] = _winsorize_series(
            nw_df["Observed_Vol_1M"], lower=0.01, upper=0.01)

        return nw_df

    # ── Cells 22-26: observed_vols_df pool ────────────────────────────────

    def _build_observed_vols_pool(
        self,
        price_df: pd.DataFrame,
        rebal_dates_file: str,
    ) -> pd.DataFrame:
        """
        Notebook cells 22-26 EXACTLY:

        Cell 22: price_df['return'] = price_df[col].pct_change(); dropna
        Cell 23: price_df['RealizedVol_1M'] = rolling(30).std(); dropna
        Cell 24: start_date = price_df.index.min()  ← uses EARLIEST available date
                 end_date   = price_df.index.max()
                 weekly_rebal_dates = all rebal dates in [start_date, end_date]
        Cell 26: observed_vols_df = realized_vol per weekly_rebal_date; dropna

        CRITICAL: Uses ALL rebal dates (back to 1995), not just post-2004.
        By Jan 2020 this gives ~1255 rows of history for the quantile bucketing.
        """
        import pandas as pd

        # Cell 22-23: price_df with returns and rolling vol, then dropna
        p = price_df.copy()
        p['return'] = p.iloc[:, 0].pct_change()
        p = p.dropna()
        p['RealizedVol_1M'] = p['return'].rolling(window=30).std()
        p = p.dropna()

        # Cell 24: weekly_rebal_dates from FULL rebal file, using price_df date range
        rebal_raw = pd.read_excel(rebal_dates_file)
        rebal_raw['Date'] = pd.to_datetime(rebal_raw['Date'])
        start = p.index.min()
        end   = p.index.max()
        weekly_rebal_dates = rebal_raw.loc[
            (rebal_raw['Date'] >= start) & (rebal_raw['Date'] <= end), 'Date'
        ].tolist()

        # Cell 26: compute observed vol per date
        obs_vols = [_realized_vol_1m(p, d) for d in weekly_rebal_dates]
        obs_df = pd.DataFrame({"Observed_Vol_1M": obs_vols}, index=weekly_rebal_dates)
        obs_df.index = pd.to_datetime(obs_df.index)
        obs_df = obs_df.dropna()

        print(f"[VolAggregator] observed_vols_df pool: {len(obs_df)} rows  "
              f"({obs_df.index[0].date()} → {obs_df.index[-1].date()})")
        return obs_df

    # ── Cell 33: quantile bucketing ───────────────────────────────────────

    def _quantile_bucketing(
        self,
        rws: pd.DataFrame,
        observed_vols_df: pd.DataFrame,
        nw_forecast_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Exact replication of notebook cell 33.
        Uses observed_vols_df (ALL weekly rebal dates) as the past-vol pool.
        Assigns VolBucket and Observed_VolBucket to rws.
        """
        n_buckets = 30
        rws = rws.copy()
        rws["VolBucket"] = np.nan
        rws["Observed_VolBucket"] = np.nan

        bucket_edges = np.linspace(0, 1, n_buckets + 1)

        def assign_bucket(vol, qt, edges, p5, p95):
            vol_clip = np.clip(vol, p5, p95)
            transformed = qt.transform(np.array(vol_clip).reshape(-1, 1)).item()
            for i in range(len(edges) - 1):
                if edges[i] <= transformed < edges[i + 1]:
                    return i + 1
            if transformed >= edges[-1]:
                return len(edges) - 1
            return np.nan

        for idx, date in enumerate(rws["RebalDate"]):
            # Past-only: observed vols STRICTLY before this date
            past_obs_vols = observed_vols_df.loc[
                observed_vols_df.index < date, "Observed_Vol_1M"
            ]

            if len(past_obs_vols) < n_buckets:
                continue

            # Notebook: p5=percentile(past,0), p95=percentile(past,95)
            p5, p95 = np.percentile(past_obs_vols, [0, 95])
            clipped_vols = np.clip(past_obs_vols, p5, p95)

            qt = QuantileTransformer(
                output_distribution="uniform",
                n_quantiles=min(len(clipped_vols), 1000),
            )
            qt.fit_transform(clipped_vols.values.reshape(-1, 1))

            wgt_vol = rws.at[idx, "WgtVol_1M"]
            obs_vol = rws.at[idx, "Observed_Vol_1M"]

            rws.at[idx, "VolBucket"] = assign_bucket(wgt_vol, qt, bucket_edges, p5, p95)
            rws.at[idx, "Observed_VolBucket"] = assign_bucket(obs_vol, qt, bucket_edges, p5, p95)

        return rws

    # ── Cell 66: rolling exp calibration ─────────────────────────────────

    def _rolling_exp_calibration(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Notebook cell 66: window=156, fit exp_func(VolBucket → Observed_VolBucket)
        using median per bucket. Apply point-wise: Calibrated_VolBucket = a*exp(b*VolBucket)
        """
        window = 156
        a_list, b_list = [], []

        for i in range(len(df)):
            if i < window:
                a_list.append(np.nan)
                b_list.append(np.nan)
                continue

            hist = df.iloc[i - window: i]
            bucket_medians = (
                hist.groupby("VolBucket")
                .agg({"Observed_VolBucket": "median"})
                .reset_index()
            )

            xdata = bucket_medians["VolBucket"].values
            ydata = bucket_medians["Observed_VolBucket"].values

            try:
                popt, _ = curve_fit(_exp_func, xdata, ydata, p0=(1, 0.05), maxfev=10000)
                a_list.append(popt[0])
                b_list.append(popt[1])
            except Exception:
                a_list.append(np.nan)
                b_list.append(np.nan)

        df = df.copy()
        df["a_param"] = a_list
        df["b_param"] = b_list

        # Calibrated_VolBucket = a * exp(b * VolBucket)
        df["Calibrated_VolBucket"] = (
            np.exp(df["b_param"] * df["VolBucket"]) * df["a_param"]
        )
        return df

    # ── Cell 68: rolling min-max scaling ──────────────────────────────────

    def _rolling_minmax_scale(self, df: pd.DataFrame) -> pd.DataFrame:
        """Notebook cell 68: rolling window=156, min_periods=52."""
        calib = df["Calibrated_VolBucket"]
        roll_min = calib.rolling(window=156, min_periods=52).min()
        roll_max = calib.rolling(window=156, min_periods=52).max()
        df = df.copy()
        df["CalibVol_Scaled"] = (calib - roll_min) / (roll_max - roll_min)
        return df
