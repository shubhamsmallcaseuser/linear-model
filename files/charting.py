"""
charting.py — Reusable plots for the vol-regime pipeline.
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np
from typing import Optional


def _quarterly_xaxis(ax: plt.Axes) -> None:
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")


def plot_regime_signal(
    signal_df: pd.DataFrame,
    ticker: str,
    output_path: Optional[str] = None,
) -> None:
    """
    Plot the final smoothed vol-regime signal alongside observed vol.
    """
    fig, ax = plt.subplots(figsize=(14, 6))

    ax.plot(signal_df["RebalDate"], signal_df["Vol_Regime_Monthly"],
            lw=1.5, label="Vol Regime (4-week MA)")
    ax.plot(signal_df["RebalDate"], signal_df["Vol_Regime_Smooth"],
            lw=1.5, label="Vol Regime (EWMA)")
    ax.plot(signal_df["RebalDate"], signal_df["Observed_Vol_1M"] * 10,
            lw=1.2, alpha=0.5, linestyle="--", label="Observed Vol 1M (×10)")

    _quarterly_xaxis(ax)
    ax.set_xlabel("Date")
    ax.set_ylabel("Calibrated Volatility (Scaled)")
    ax.set_title(f"Volatility Regime Signal — {ticker}")
    ax.legend(loc="upper left", frameon=True, fancybox=True, shadow=True)
    ax.grid(True, linestyle="--", alpha=0.3)
    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=120)
    plt.show()
    plt.close()


def plot_predicted_vs_observed(
    weighted_df: pd.DataFrame,
    ticker: str,
    output_path: Optional[str] = None,
) -> None:
    """
    Plot motif-weighted predicted vol vs observed vol over time.
    """
    fig, ax = plt.subplots(figsize=(14, 6))

    ax.plot(weighted_df["RebalDate"], weighted_df["WgtVol_1M"],
            lw=1.5, label="Weighted Predicted Vol")
    ax.plot(weighted_df["RebalDate"], weighted_df["Observed_Vol_1M"],
            lw=1.5, linestyle="--", label="Observed Vol")

    _quarterly_xaxis(ax)
    ax.set_xlabel("Date")
    ax.set_ylabel("1-Month Volatility")
    ax.set_title(f"Predicted vs Observed Volatility — {ticker}")
    ax.legend()
    ax.grid(True, linestyle="--", alpha=0.3)
    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=120)
    plt.show()
    plt.close()


def plot_universe_ranking(
    ranking_df: pd.DataFrame,
    output_path: Optional[str] = None,
) -> None:
    """
    Horizontal bar chart ranking tickers by latest vol-regime score.
    Green = low volatility, Red = high volatility.
    """
    df = ranking_df.sort_values("LatestSignal", ascending=True)
    colors = plt.cm.RdYlGn_r(np.linspace(0.1, 0.9, len(df)))

    fig, ax = plt.subplots(figsize=(10, max(4, len(df) * 0.55)))
    bars = ax.barh(df["Ticker"], df["LatestSignal"], color=colors, edgecolor="white")

    # Annotate bar values
    for bar, val in zip(bars, df["LatestSignal"]):
        ax.text(
            bar.get_width() + 0.005, bar.get_y() + bar.get_height() / 2,
            f"{val:.3f}", va="center", fontsize=9,
        )

    ax.set_xlim(0, 1.12)
    ax.set_xlabel("Vol Regime Signal (0 = low vol, 1 = high vol)")
    ax.set_title("Universe Volatility Ranking — Latest Signal")
    ax.axvline(0.5, color="gray", linestyle="--", alpha=0.5, label="Mid-point (0.5)")
    ax.legend()
    ax.grid(True, axis="x", linestyle="--", alpha=0.3)
    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=120)
    plt.show()
    plt.close()


def plot_cross_ticker_heatmap(
    all_signals: dict,  # {ticker: signal_df}
    output_path: Optional[str] = None,
) -> None:
    """
    Heatmap of smoothed vol-regime signal across all tickers over time.
    """
    # Build a wide DataFrame: dates × tickers
    frames = {}
    for ticker, df in all_signals.items():
        s = df.set_index("RebalDate")["Vol_Regime_Smooth"]
        frames[ticker] = s

    wide = pd.DataFrame(frames).sort_index()
    wide = wide.resample("ME").last().dropna(how="all")

    fig, ax = plt.subplots(figsize=(16, max(3, len(wide.columns) * 0.5)))
    im = ax.imshow(
        wide.T.values,
        aspect="auto",
        cmap="RdYlGn_r",
        vmin=0, vmax=1,
    )

    # X-axis: dates
    ax.set_xticks(range(len(wide.index)))
    ax.set_xticklabels(
        [d.strftime("%b %y") for d in wide.index],
        rotation=45, ha="right", fontsize=7,
    )
    # Y-axis: tickers
    ax.set_yticks(range(len(wide.columns)))
    ax.set_yticklabels(wide.columns, fontsize=9)

    plt.colorbar(im, ax=ax, label="Vol Regime Signal")
    ax.set_title("Cross-Ticker Volatility Regime Heatmap (green = calm, red = stressed)")
    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=120)
    plt.show()
    plt.close()
