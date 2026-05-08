"""
output_writer.py — Saves all outputs to Excel/CSV.
Note: first_of_month_df is already monthly-sampled by VolAggregator.
"""

import os
import pandas as pd
from typing import Dict


class OutputWriter:
    def __init__(self, config):
        self.cfg = config
        os.makedirs(self.cfg.output_dir, exist_ok=True)

    def save_signals(self, all_signals: Dict[str, pd.DataFrame], signal_start: str) -> str:
        """Save per-ticker signals (already monthly) filtered to signal_start."""
        path = os.path.join(self.cfg.output_dir, self.cfg.output_excel)

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            for ticker, df in all_signals.items():
                if df.empty:
                    continue
                df = df.copy()
                df["RebalDate"] = pd.to_datetime(df["RebalDate"])
                # Filter to signal_start — data is already monthly
                output = df[df["RebalDate"] >= pd.Timestamp(signal_start)].reset_index(drop=True)
                sheet = ticker.replace(".", "_")[:31]
                output.to_excel(writer, sheet_name=sheet, index=False)

        print(f"[OutputWriter] Signals saved → {path}")
        return path

    def save_ranking(self, ranking_df: pd.DataFrame, picks_df: pd.DataFrame) -> str:
        path = os.path.join(self.cfg.output_dir, self.cfg.ranking_excel)
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            ranking_df.to_excel(writer, sheet_name="Full_Ranking", index=False)
            picks_df.to_excel(writer, sheet_name="Least_Volatile_Picks", index=False)
        print(f"[OutputWriter] Ranking saved → {path}")
        return path

    def save_panel(self, panel: pd.DataFrame) -> str:
        path = os.path.join(self.cfg.output_dir, "signal_panel.csv")
        panel.to_csv(path)
        print(f"[OutputWriter] Panel saved → {path}")
        return path
