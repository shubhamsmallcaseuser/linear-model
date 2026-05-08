"""
data_loader.py — Loads price data and rebal dates exactly as the notebook does.

CRITICAL (notebook cell 1):
    getTradingDatesDataFrame(startDate=closeDf.first_valid_index())
    NOT startDate=cfg.start_date.

    The price DataFrame must start from 1995 (first valid price), not 2004.
    mk.Match needs the full history back to 1995 to find analogues for
    rebalDates starting at 2004. With only 2004+ data, it finds completely
    different analogues → different WgtVol_1M → everything downstream diverges.
"""

import sys
import os
import numpy as np
import pandas as pd
from typing import List, Tuple


class DataLoader:
    def __init__(self, config):
        self.cfg = config
        self._add_parent_to_path()

    def _add_parent_to_path(self):
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)

    def load_all(self) -> Tuple[pd.DataFrame, List[pd.Timestamp]]:
        price_df = self._load_prices()
        rebal_dates = self._load_rebal_dates(price_df)
        return price_df, rebal_dates

    def _load_prices(self) -> pd.DataFrame:
        """
        Load close prices from first_valid_index (not cfg.start_date).
        Tries QuantBacktester first, falls back to direct Excel read.
        """
        try:
            import Python_Scripts.QuantBacktester as qd
            reader = qd.ExcelInputReader()
            raw = reader.getDataFrame(self.cfg.price_file, sheetName=self.cfg.price_sheet)
            raw.set_index("Date", inplace=True)
            raw.index = pd.to_datetime(raw.index)

            # ── NOTEBOOK EXACT: use first_valid_index(), NOT cfg.start_date ──
            first_valid = raw.first_valid_index()
            all_dates_df = reader.getTradingDatesDataFrame(
                excelFile=self.cfg.trading_days_file,
                sheetName=self.cfg.trading_days_sheet,
                startDate=first_valid,           # 1995-11-03, not 2004-01-01
            )
            all_dates_df.reset_index(drop=True, inplace=True)

            merger = qd.Merger()
            price_df = merger.getMergedBymethodDf(all_dates_df, raw)

            if "Date" in price_df.columns:
                price_df.set_index("Date", inplace=True)

        except ImportError:
            price_df = self._load_prices_direct()

        price_df.index = pd.to_datetime(price_df.index)
        price_df.sort_index(inplace=True)

        # Keep only requested tickers
        available = [t for t in self.cfg.tickers if t in price_df.columns]
        missing   = set(self.cfg.tickers) - set(available)
        if missing:
            print(f"[DataLoader] WARNING — tickers not found: {missing}")
            print(f"[DataLoader] Available: {price_df.columns.tolist()}")
        if not available:
            raise ValueError(
                f"None of the requested tickers found. "
                f"Available: {price_df.columns.tolist()}"
            )

        price_df = price_df[available].copy()
        print(f"[DataLoader] Prices loaded: {available}")
        print(f"[DataLoader]   Range: {price_df.index[0].date()} → {price_df.index[-1].date()}")
        print(f"[DataLoader]   Rows:  {len(price_df)} (full history for motif matching)")
        return price_df

    def _load_prices_direct(self) -> pd.DataFrame:
        """
        Fallback: read INDTradingDays.xlsx directly (2-row metadata header).
        Returns ALL rows from first_valid_index forward (full history).
        """
        raw = pd.read_excel(
            self.cfg.price_file,
            sheet_name=self.cfg.price_sheet,
            header=None,
            skiprows=2,
        )
        raw.columns = raw.iloc[0]
        raw = raw.iloc[1:].reset_index(drop=True)
        raw = raw.drop(columns=[c for c in raw.columns if not isinstance(c, str)],
                       errors='ignore')
        raw['Date'] = pd.to_datetime(raw['Date'])
        raw = raw.set_index('Date')
        raw = raw.apply(pd.to_numeric, errors='coerce')

        # Simulate getMergedBymethodDf: reindex to trading calendar + ffill
        td = pd.read_excel(
            self.cfg.trading_days_file,
            sheet_name=self.cfg.trading_days_sheet,
            header=None,
            skiprows=2,
        )
        td.columns = td.iloc[0]
        td = td.iloc[1:].reset_index(drop=True)
        td = td.drop(columns=[c for c in td.columns if not isinstance(c, str)],
                     errors='ignore')
        td['Date'] = pd.to_datetime(td['Date'])
        trading_days = td['Date'].dropna().sort_values()

        # ── NOTEBOOK EXACT: start from first_valid_index ──
        first_valid = raw[self.cfg.tickers[0]].first_valid_index()
        if first_valid is None:
            first_valid = raw.index[0]

        td_filtered = trading_days[trading_days >= first_valid]
        price_df = raw.reindex(td_filtered).ffill()
        return price_df

    def _load_rebal_dates(self, price_df: pd.DataFrame) -> List[pd.Timestamp]:
        """
        Notebook cell 2: rebalDates from W_allRebal.xlsx,
        filtered to [cfg.start_date, price_df.index.max()].
        (rebalDates filter uses 2004, but price_df goes back to 1995)
        """
        rebal_raw = pd.read_excel(self.cfg.rebal_dates_file)
        rebal_raw['Date'] = pd.to_datetime(rebal_raw['Date'])

        start = pd.Timestamp(self.cfg.start_date)   # 2004-01-01
        end   = price_df.index.max()

        dates = rebal_raw.loc[
            (rebal_raw['Date'] >= start) & (rebal_raw['Date'] <= end), 'Date'
        ].tolist()

        print(f"[DataLoader] Rebal dates: {len(dates)}"
              f"  |  {dates[0].date()} → {dates[-1].date()}")
        return dates
