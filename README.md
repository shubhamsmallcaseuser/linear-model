# Low-Volatility Equity Strategy — NSE Top-50

This project builds a forward-looking volatility regime signal for Indian equities and uses it to construct a low-volatility equity portfolio, benchmarked primarily against smallcase's SCSB_0003. **This README is a knowledge-transfer (KT) document** — the author is leaving the firm, and it is written so a successor with zero prior context can become productive in one sitting.

Every claim below was checked against the actual notebook code, the actual output data files, or both — not just repeated from the existing Word reports. Where a prior claim didn't hold up, it is flagged explicitly rather than silently repeated. That verification work is the main value of this rewrite; see Section 2 and Section 5 for the specific corrections.

---

## 1. What This Project Is

**Goal:** forecast which stocks (within the NSE Top-50 by market cap) will be *calmest* over the next month, and use that to build a low-volatility equity portfolio that beats a passive benchmark.

**Method, in one sentence:** instead of fitting a parametric volatility model (GARCH, HAR), ask *"which historical 45-day periods looked most like today's volatility fingerprint, and what happened to volatility and returns in the month that followed?"* — this is **MASS** (Mueen's Algorithm for Similarity Search), a non-parametric pattern-matching approach. The empirical answer becomes the forecast, aggregated and calibrated into a single signal: **`Vol_Regime_Smooth`**, a `[0, 1]`-bounded number per ticker per month (0 = calm, 1 = stressed).

**Scope:** NSE Top-50 Indian equities by market capitalisation, monthly rebalancing, backtest period January 2020 – February 2026 (some signal history goes back to 2005/1995 for motif matching). Primary benchmark: SCSB_0003 (smallcase's Low Risk Smart Beta product, 8.51% CAGR over the period).

The project evolved through three phases — understanding this arc will save you from re-discovering dead ends already explored:

| Phase | Period | What happened |
|---|---|---|
| **1 — Foundations** | Jun–Oct 2025 | GARCH(1,1)/FIGARCH and a HAR-RS (Heterogeneous Autoregressive Realised Semivariance) weekly signal were explored for a Nifty/Gold asset-allocation (AA) smallcase. Per the Phase-1 research brief, HAR-RS gave weak out-of-sample R² at weekly frequency and too much turnover for an AA product. MASS motif matching was introduced as a non-parametric alternative, tested alongside a Path-Shadowing Monte Carlo (PSMC) variant. **Caveat:** see Section 5 — no notebook in the current repo could be located that actually implements the HAR-RS model; the only surviving evidence of it is prose/formulas in the Word doc. |
| **2 — Signal calibration & strategy design** | Nov 2025–Feb 2026 | Focus shifted from AA (Nifty/Gold switching) to cross-sectional low-vol equity selection within NSE Top-50. Discovered that predicted-vs-observed volatility (bucketed) fits an **exponential curve** — this became Stage 7 of the signal pipeline (Section 4). Built and backtested three portfolio strategies: Fixed-10, Dynamic Adaptive, Gap+Regime. |
| **3 — Production & reporting** | Mar–Jun 2026 | Refactored notebook logic into the modular `files/` pipeline. Added `DbConnections` (PostgreSQL/MongoDB) — built but confirmed **not called anywhere in `files/`** (grep-verified). Generated the formal research report. |

---

## 2. Headline Result — and Important Caveats

> **Dynamic InvVol is the best strategy found: 17.24% CAGR, 0.95 Sharpe, 1.34 Sortino, -41.53% max drawdown, +873 bps CAGR alpha over SCSB_0003 (8.51% CAGR), backtested Jan 2020–Feb 2026.**

**This number is genuinely well-supported** — it is independently confirmed in three places that were checked separately: the `Low_Vol_Strategy_Research_Report.docx`, the executed output cells of `strategy_comparison.ipynb`, and the `Performance_Metrics` sheet of the generated `strategy_comparison.xlsx`. All three agree to the basis point. This is the one number in the whole project you can cite with full confidence.

**Caveats a successor should know before relying on it further:**

1. **The NSE Top-50 universe used for the whole 6-year backtest is not a proper point-in-time universe.** `mcap_based_universe_202602251340.csv` — the file the "Top-50" label refers to — was independently inspected and is **not** a 50-row snapshot at all. It's a full historical market-cap table (526,104 rows, ~3,000 tickers per date, spanning 2005–2026). Whatever Top-50 filtering actually drives the backtest happens downstream (in a notebook, applying a mcap-rank cutoff as of the latest date) and is applied **retroactively across the entire 2020–2026 backtest** — i.e. today's biggest 50 companies are assumed to have also been the biggest 50 in 2020. This is a forward-looking-bias risk that is *already flagged* in the research report, but the underlying data file is more clearly a full-market table than "a Top-50 snapshot," which is worth correcting in your own mental model.
2. **The ~0.10–0.11 correlation between the signal and realised volatility, often cited as evidence the signal is "intentionally low but valid," does not reproduce to one consistent number.** Independent notebook checks found: `Monthly_signal_analysis.ipynb` outputs 0.1522 (simple/IDW) and 0.1119 (Nadaraya-Watson); the Phase-1 research doc quotes 0.1143 and 0.1031; and a near-duplicate motif notebook (`extended_analysis.ipynb` — see caveat 3) shows completely different values ranging from -0.39 to +0.66 depending on ticker/window. Treat "~0.11" as an order-of-magnitude characterisation, not a precise, reproducible statistic — it appears to vary by ticker, sample window, and notebook version.
3. **Several notebooks are miscredited in the previous KT document** and, by extension, in earlier drafts of this README. Verified by direct inspection:
   - `top50mcap_analysis.ipynb` does **not** contain the Fixed-10/Dynamic/Gap-Regime comparison it was credited with. It's a pasted copy of a signal-calibration script plus an EqualWeight-vs-InvVol backtest. The "avg 7.6 stocks/month" statistic actually lives in `dynamic_low_vol_selection.ipynb`; the "28.9% turnover" statistic actually lives in `strategy_comparison.ipynb`.
   - `Monthly_rebal.ipynb` does **not** combine all three strategies into a unified backtest. It is structurally near-identical to `Weekly_rebal_motifs.ipynb` — the same MASS motif-matching pipeline, not a strategy-comparison notebook.
   - `extended_analysis.ipynb` is **not** macro/FX/fixed-income feature engineering work. It is a near-verbatim duplicate of the motif-matching pipeline (same `mk.Match`, same window/top-k logic). The actual macro-variable scoping work exists only as a to-do list inside `Volatility Research for AA smallcases.docx` — it was never started in code.
   - The corrected notebook tiering is in Section 8 below.
4. **`LinearModel.py`** (listed as part of the "core library" in the prior CLAUDE.md/AGENTS.md architecture tables) is confirmed **orphaned** — a repo-wide grep found zero imports of it from any notebook or pipeline file.

None of these caveats change the headline number — they change how much weight to put on the *supporting* narrative around it (universe construction, signal-quality metric, and which notebook to open for which sub-topic).

---

## 3. Core Concepts Glossary

| Term | Definition |
|---|---|
| **MASS** | Mueen's Algorithm for Similarity Search — computes a z-normalised Euclidean distance profile between a query subsequence and every window of a longer target series. Implemented in `Python_Scripts/mass.py` via `np.convolve`-based rolling correlation, not FFT (despite some docs describing it as FFT-based) and not DTW. |
| **Motif / analogue** | A historical 45-trading-day window whose squared-return pattern most closely matches the current 45-day window, per MASS distance. |
| **`Vol_Regime_Smooth`** | The final, production signal — EWM-smoothed (α=0.15), `[0,1]`-bounded, monthly-sampled volatility regime indicator. 0 = calm, 1 = stressed. All portfolio construction uses this column. |
| **IDW (Inverse-Distance Weighting)** | Aggregation scheme combining the 5 nearest analogues: `weight_k = (1/distance_k) / Σ(1/distance_j)`. Closer analogues get more weight. |
| **NW (Nadaraya-Watson) forecast** | An alternative kernel-weighted aggregation of analogues, tested against IDW; both perform similarly (see caveat 2 above on the exact correlation numbers). |
| **Exponential calibration (Stage 7)** | The single most important, least obvious step in the pipeline. The median *observed* volatility per *predicted*-volatility bucket empirically fits `y = a·exp(b·x)`; the pipeline refits `a, b` on a rolling window and applies the curve to correct systematic under-prediction of high-vol regimes. Confirmed implemented in `files/vol_aggregator.py::_rolling_exp_calibration` / `_exp_func`. |
| **Look-ahead bias avoidance** | The quantile bucketing step (`QuantileTransformer`) and the exponential calibration step are both fit on strictly past data only (rolling windows), never on the full sample — confirmed in `files/vol_aggregator.py`. |
| **Fixed-10 / Dynamic Adaptive / Gap+Regime** | The three portfolio-construction strategies compared — see Section 5. |
| **CAGR / Sharpe / Sortino / Calmar / Max DD** | Standard risk-adjusted performance metrics; all Sharpe/Sortino figures in this project assume a 0% risk-free rate. Calmar = CAGR / |Max DD|. |
| **bps** | Basis points; 100 bps = 1 percentage point. Used throughout for alpha (CAGR difference vs. benchmark). |

---

## 4. Pipeline / Methodology — the 8-Stage Signal

All strategies consume one signal, produced by `files/vol_aggregator.py::VolAggregator`, driven by `Python_Scripts/mass.py::Match`. Every stage below was confirmed present in the actual code, with the actual function/variable names:

```
Daily NSE closing prices (currently Excel only — see Section 10)
        │  aligned to official trading calendar (TradingDays.xlsx)
        ▼
Stage 1  Data Ingestion           full history loaded — MASS needs long history for analogues
Stage 2  Squared Returns          daily log-returns squared → non-negative variance proxy
Stage 3  MASS Motif Matching      Python_Scripts/mass.py::Match(window=45, threshold=0.50);
                                  top-5 analogues selected downstream via files/motif_engine.py
                                  (mass.py itself has no built-in "top_k" — it's applied by the caller)
Stage 4  Forward Statistics       files/motif_engine.py::_attach_forward_stats — for each of the
                                  5 analogues: 1-month forward Vol, MeanRet, RealizedVol, Skew, Kurt
Stage 5  IDW Aggregation          files/vol_aggregator.py::_weighted_aggregation —
                                  weight_k = (1/distance_k) / Σ(1/distance_j)
Stage 6  Winsorise + Bucket       _winsorize_series (scipy winsorize) →
                                  _quantile_bucketing (QuantileTransformer, strictly past-only) → VolBucket
Stage 7  Exponential Calibration  ★ KEY INSIGHT ★ — _rolling_exp_calibration / _exp_func = a·exp(b·x),
                                  scipy curve_fit, rolling 156-week refit → Calibrated_VolBucket
Stage 8  Normalise + Smooth       _rolling_minmax_scale (156w, min_periods=52) → CalibVol_Scaled ∈ [0,1]
                                  → Vol_Regime_Monthly (4w rolling mean)
                                  → Vol_Regime_Smooth = CalibVol_Scaled.ewm(alpha=0.15).mean()  ← used everywhere
```

`Stage 7` is documented with its discovery process in `Monthly_signal_analysis.ipynb` — read that notebook before modifying the calibration logic. (Note: that notebook never actually uses the string `Vol_Regime_Smooth` — it works one level down, on the bucket/calibration math itself. The final signal name is only assembled in `files/vol_aggregator.py` and the strategy notebooks.)

**Signal cache statistics (verified directly from `ticker_signals_cache.xlsx`):** 13,563 ticker-date rows, 78 unique tickers, 304 unique monthly rebalance dates (full history 2005-01-07 to 2026-02-01), `Vol_Regime_Smooth` confirmed bounded in `[0.0018, 0.9964]` with zero NaNs.

---

## 5. Approaches / Strategies Tried

| Approach | What it does | Status | Verified primary file |
|---|---|---|---|
| **GARCH(1,1) / FIGARCH** | Parametric volatility forecasting on Nifty. | Superseded — implemented and functional (`Python_Scripts/garch.py`, `garch_upgraded.py`), but not part of the active signal pipeline. | `garch_implementation.ipynb`, `FIGARCH_implementation.ipynb`, `FIGARCH_model.ipynb` |
| **HAR-RS** | Weekly realised-semivariance forecast with lagged RS/ATR features, used for Nifty/Gold switching. | **Claimed in the Phase-1 research doc; no implementing notebook found in the current repo.** Described in prose/formula form only in `Volatility Research for AA smallcases.docx`. Treat any HAR-RS-specific number as unverifiable against current source. | Not found — flagged, not fabricated |
| **Motif + PSMC (IDW / NW aggregation)** | MASS motif matching combined with two candidate aggregation schemes (inverse-distance vs. Nadaraya-Watson kernel). | Confirmed implemented — `robust_nw_forecast` and IDW `weighted_avg` both present in `Motif+PSMC.ipynb`. The specific ~0.11 correlation figures could not be located in that notebook's own outputs (see caveat 2, Section 2). | `Motif+PSMC.ipynb` |
| **8-stage `Vol_Regime_Smooth` pipeline** | The production signal (Section 4). | Confirmed implemented exactly as documented, in `files/vol_aggregator.py`. | `files/vol_aggregator.py`, `Monthly_signal_analysis.ipynb` |
| **Fixed-10 (baseline)** | Rank all eligible tickers by `Vol_Regime_Smooth` ascending; take the 10 calmest; equal- or inverse-vol-weight. | Confirmed — 13.30% CAGR (EqW) / 15.56% CAGR (InvVol). | `strategy_comparison.ipynb` (comparison), signal-calibration logic reused from earlier notebooks |
| **Dynamic Adaptive (★ winner)** | Percentile filter (≤20th pct, `SIGNAL_CUTOFF_PCT=20`) + absolute cutoff (≤0.45, `SIGNAL_CUTOFF_ABS=0.45`) + ceiling of 10 (`MAX_STOCKS=10`), explicitly **no forced floor** — confirmed via docstring "hold however many pass (0 = stay flat that month)." Inverse-vol weighted. | Confirmed implemented exactly as documented — 17.24% CAGR. | `dynamic_low_vol_selection.ipynb` |
| **Gap + Regime** | NSEI 63-day rolling vol classifies calm (`<12%`)/normal/stressed (`>20%`) regimes; regime-specific gap-detection multiplier (1.5/1.8/2.5) and min/max stock bounds (5–10/7–15/10–25) find the natural "elbow" in the sorted signal. | Confirmed implemented exactly as documented — 13.44% CAGR, underperforms Dynamic. **Note:** this notebook's own output table does not itself show the comparison to "Dynamic" — that comparison only appears in `strategy_comparison.ipynb`. | `gap_regime_vol_selection.ipynb` |

**Key finding: complexity did not pay off.** Gap+Regime (9 free parameters) barely beat the 1-parameter Fixed-10 baseline (13.44% vs 13.30% CAGR) and lost decisively to the 3-parameter Dynamic strategy (13.44% vs 17.24%).

---

## 6. Result Numbers

All figures below are pulled directly from `strategy_comparison.xlsx` → sheet `Performance_Metrics` (independently confirmed against `strategy_comparison.ipynb`'s executed output cells and the research report — three-way match).

| Strategy | CAGR | Ann. Vol | Sharpe | Sortino | Max DD | Calmar |
|---|---|---|---|---|---|---|
| **Dynamic_InvVol ★ best** | **17.24%** | 18.68% | 0.95 | **1.34** | -41.53% | **0.42** |
| Fixed10_InvVol | 15.56% | 16.42% | **0.97** | 1.30 | -41.23% | 0.38 |
| Gap_Regime | 13.44% | 16.57% | 0.85 | 1.14 | -40.88% | 0.33 |
| Fixed10_EqW | 13.30% | 15.94% | 0.87 | 1.17 | -39.98% | 0.33 |
| SCET_0005 | 12.03% | 10.17% | 1.17 | 1.65 | -25.53% | 0.47 |
| SCMO_0003 | 12.77% | 20.75% | 0.69 | 0.93 | -42.52% | 0.30 |
| SCET_0013 | 8.97% | 7.92% | 1.13 | 1.54 | -21.47% | 0.42 |
| **SCSB_0003 (primary benchmark)** | 8.51% | 11.20% | 0.79 | 1.12 | -22.40% | 0.38 |

**Note on strategy names:** the actual output file uses `Dynamic_InvVol` and `Gap_Regime` (underscored) — not "Dynamic" or "Gap" alone as some earlier documents shorten them to. Use the exact names if querying the Excel/notebook outputs directly.

**Regime-conditional performance** (from the research report, not independently re-derived from a raw regime-tagged output file — treat as report-sourced): Dynamic InvVol's biggest edge over SCSB_0003 comes in stressed regimes (29.5% vs 13.9% CAGR, +1,560 bps) — precisely because the no-floor design lets it concentrate into 1–3 names when the market is turbulent.

**Year-by-year:** 2021 is the dominant alpha year (Dynamic +81.47% vs SCSB_0003 +18.96%, post-COVID recovery). 2023 is the only year SCSB_0003 edged ahead (+27.43% vs Dynamic's +25.06%) — a broad small-cap rally favoured the benchmark's wider universe. Treat any renewed broad small-cap rally as the main risk scenario for this strategy's relative performance.

**Drawdown trade-off:** all four strategies carry roughly -40% to -42% max drawdown vs SCSB_0003's -22.4%, reflecting concentration in a large-cap subset vs. the benchmark's broader small-cap exposure. Dynamic InvVol's Calmar (0.42) still exceeds SCSB_0003's (0.38).

---

## 7. Repository Structure

```
Linear Model/
├── README.md                              ← you are here
├── CLAUDE.md / AGENTS.md                  agent-facing environment/architecture notes
├── Task_List.md                           chronological task log, June 2025–May 2026, with dated deliverables
├── KT_LowVol_Strategy.docx                ★ formal KT Word document (companion to this README)
├── Low_Vol_Strategy_Research_Report.docx  ★ management-facing performance report — cite this for external numbers
├── Volatility Research for AA smallcases.docx   Phase-1 research brief (HAR-RS description, macro to-do list, manager's notes)
├── templates/                             README/KT-doc generation templates used to produce these two documents
│
├── Python_Scripts/                        shared core library, used by both notebooks and files/
│   ├── QuantBacktester.py                 ExcelInputReader, Merger, UtilsQB, IndexCalculator, IndexAnalytics,
│   │                                       Rebalance, Optimization, Ranker, StockSelector — data I/O + backtest engine
│   ├── mass.py                            MASS, Match, DistanceProfile, SignalAnalysis — the motif-matching algorithm
│   ├── tsa.py                             Preprocess, Returns, FractionalDifferencing, Test (stationarity/diagnostics)
│   ├── arma.py                            ModelSelection, AR/MA/ARMA, Model, SimulateFD (Phase 1, not in active pipeline)
│   ├── garch.py / garch_upgraded.py       Volatility/Mean/Distribution/Model (GARCH/FIGARCH via `arch`; superseded)
│   ├── gmm.py                             GMM, EM, NormalDist, MMCompSelection (used by gap_regime_vol_selection.ipynb)
│   ├── ST.py                              getSupertrend, getRsiBasedValues, getEMA — RSI/Supertrend index helpers
│   ├── PropsectTheory.py                  (file is misspelled on disk, no "s") — ProspectTheory, ProbabilityOfPastReturn;
│   │                                       behavioural-finance value function, research-only, unused in active pipeline
│   └── db_connections.py                  DbConnections — PostgreSQL + MongoDB singleton; confirmed NOT called
│                                           anywhere in files/ (grep-verified) — built but not wired in
│
├── files/                                 production pipeline — modular refactor of the notebook logic
│   ├── config.py                          PipelineConfig dataclass — single source of truth for tickers/dates/paths/motif params
│   ├── main.py                            entry point: load data → motif match → aggregate → rank → export
│   ├── data_loader.py                     DataLoader — reads INDTradingDays.xlsx + W_allRebal.xlsx; confirmed
│   │                                       purely Excel-based, zero PostgreSQL/SQL code present
│   ├── motif_engine.py                    MotifEngine — wraps mass.Match, computes forward-1M stats
│   ├── vol_aggregator.py                  VolAggregator — the 8-stage signal pipeline (Section 4), most complex module
│   ├── universe_ranker.py                 UniverseRanker — cross-sectional ranking → pick lists
│   ├── output_writer.py                   OutputWriter — Excel/CSV export
│   ├── charting.py                        regime plots, predicted-vs-observed, ranking bar charts, heatmaps
│   └── output/                            pipeline outputs land here
│
├── data/                                   input data (Excel)
│   ├── Universe/INDTradingDays.xlsx         NSE daily closes, sheet "Close"
│   ├── Universe/TradingDays.xlsx            official NSE trading calendar
│   └── RSI/Final/NSEI/W_allRebal.xlsx       weekly rebalancing dates
│
├── ticker_signals_cache.xlsx               signal cache — 13,563 rows, 78 tickers, 304 dates (verified)
├── strategy_comparison.xlsx                full backtest results — 11 sheets incl. Performance_Metrics, Combined_Index,
│                                            Turnover, Regime_Analysis, Calendar_Returns, per-strategy weight sheets
├── dynamic_low_vol_selection.xlsx          Dynamic strategy detail — 5 sheets incl. Full_Scoring, Weight_Matrix
├── gap_regime_vol_selection.xlsx           Gap+Regime strategy detail — 6 sheets
├── monthly_low_vol_selection.xlsx          Fixed-10 reference portfolio — 6 sheets
├── mcap_based_universe_202602251340.csv    ⚠ full market-cap history (526,104 rows, ~3,000 tickers), NOT a
│                                            pre-filtered Top-50 snapshot despite the filename/prior docs implying so
├── smoothed_signal.xlsx / smoothed_signal_new.xlsx   early single-ticker validation snapshots (69 rows each) —
│                                            smaller/older than the full 304-date production cache above
└── *.ipynb                                 15+ research notebooks — see Section 8 for which ones matter
```

---

## 8. Notebook Reading Guide (Corrected)

There are 15+ notebooks. **You do not need to read all of them.** This tiering was corrected against what each notebook was directly confirmed to contain — several notebooks were previously mis-tiered (see Section 2, caveat 3).

### Tier 1 — Must read (in this order)
| # | Notebook | Confirmed to contain |
|---|---|---|
| 1 | `Monthly_signal_analysis.ipynb` | Bucket analysis of predicted vs. observed vol; the `exp_func = a·exp(b·x)` calibration discovery with `curve_fit`; a rolling/expanding calibration fit. Read before touching Stage 7. (Does **not** itself discuss `Vol_Regime_Smooth` by name — that's assembled downstream.) |
| 2 | `strategy_comparison.ipynb` | The full 4-strategy vs. 4-benchmark comparison — confirmed exact match to `strategy_comparison.xlsx` and the research report (Section 6 table). This is the notebook the headline result traces back to. |
| 3 | `dynamic_low_vol_selection.ipynb` | The winning strategy's exact filter logic (`SIGNAL_CUTOFF_PCT=20`, `SIGNAL_CUTOFF_ABS=0.45`, `MAX_STOCKS=10`, no floor), inverse-vol weighting, and the 7.6-stocks/month statistic. |
| 4 | `Weekly_rebal_motifs.ipynb` | The original MASS motif-matching notebook, step by step: `mk.Match(rvDf, rebalDate, windowSize=45, threshold=0.50)`, top-5 analogue extraction, forward-1M stats. Read this to understand/modify the signal at the algorithm level. |

### Tier 2 — Read if extending the work
| Notebook | Why |
|---|---|
| `gap_regime_vol_selection.ipynb` | Confirmed regime thresholds (calm `<12%`, stressed `>20%`) and gap-multiplier logic — read to understand *why* the more complex approach still underperformed Dynamic (comparison itself only visible in `strategy_comparison.ipynb`, not here). |
| `Motif+PSMC.ipynb` | IDW vs. Nadaraya-Watson kernel weighting comparison — confirmed both aggregation functions exist here; treat any specific correlation number from this notebook with the caveat in Section 2. |
| `Backtest_1.ipynb` | Early weekly Nifty/Gold asset-allocation backtest. Confirmed: uses `QuantBacktester.IndexCalculator`, loads a pre-computed signal from `smoothed_signal.xlsx`. **Not confirmed:** any in-notebook HAR-RS model code — it consumes an already-built signal rather than deriving one. Useful for understanding the AA backtest mechanics, not for the HAR-RS story. |

### Tier 3 — Skip / superseded (confirmed duplicative or obsolete)
| Notebook | Why you can skip it |
|---|---|
| `top50mcap_analysis.ipynb` | **Corrected tiering** — does not contain the strategy comparison it was previously credited with; it's a calibration-script copy plus an EqW-vs-InvVol test already superseded by `strategy_comparison.ipynb`. |
| `Monthly_rebal.ipynb` | **Corrected tiering** — structurally duplicates `Weekly_rebal_motifs.ipynb`'s motif pipeline; does not combine the three strategies as previously claimed. |
| `extended_analysis.ipynb` | **Corrected tiering** — not macro/FX work; another near-duplicate of the motif pipeline. If you're asked to start the macro-variable extension, the actual starting point is the to-do list in `Volatility Research for AA smallcases.docx`, not this notebook. |
| `FIGARCH_implementation.ipynb`, `FIGARCH_model.ipynb`, `garch_implementation.ipynb`, `LM.ipynb`, `model playground.ipynb` | Confirmed early/duplicated Phase-1 scratch work (same boilerplate imports, GARCH/FIGARCH family). Superseded by the MASS approach. Only relevant if reviving GARCH-family models. |

---

## 9. Environment Setup & How to Run

### 9.1 Prerequisites
- Python virtual environment at `.venv/` (already configured in the repo).
- Windows path conventions — all absolute paths in `files/config.py` currently point to `D:\Linear Model\...`.
- `eikon` (Refinitiv) requires a running Eikon/Workspace desktop app for live data — not needed for Excel-only / offline use.

### 9.2 Setup Steps
```bash
# 1. Activate the virtual environment
.venv/Scripts/activate          # Windows

# 2. Install dependencies (if needed)
pip install -r requirements.txt

# 3. Create local-only database configs (not in repo, and not currently used by files/ — see caveat below)
#    db_config.yaml, central_config_all.yaml — format documented in Python_Scripts/db_connections.py

# 4. Verify input data exists:
#    data/Universe/INDTradingDays.xlsx, data/Universe/TradingDays.xlsx,
#    data/RSI/Final/NSEI/W_allRebal.xlsx

# 5. Run the production pipeline
cd files
python main.py
```

### 9.3 Data Files Required
| File | Location | Used for |
|---|---|---|
| `INDTradingDays.xlsx` | `data/Universe/` | NSE daily closes, sheet `Close` |
| `TradingDays.xlsx` | `data/Universe/` | Official NSE trading calendar |
| `W_allRebal.xlsx` | `data/RSI/Final/NSEI/` | Weekly rebalancing dates |

Configuration lives entirely in `files/config.py` (`PipelineConfig` dataclass) — edit tickers, date ranges, motif parameters (`motif_window=45`, `motif_top_k=5`, `motif_threshold=0.50`), and file paths there. All paths are absolute and hardcoded to `D:\Linear Model\...` — moving the project requires editing every path in this one file.

**Data refresh caveat:** `files/data_loader.py` is confirmed to read Excel exclusively — there is no PostgreSQL/SQL code path anywhere in it, despite `Python_Scripts/db_connections.py` (`DbConnections`, PostgreSQL + MongoDB) existing as a standalone, working module. If you want live data, you must wire `DbConnections` into `data_loader.py` yourself — it is not a config flag away.

---

## 10. Known Gaps & Pending Work

### Must address before trusting/extending the headline result further
| Task | Status | Where to look |
|---|---|---|
| Point-in-time universe reconstitution | **Not started.** Confirmed `mcap_based_universe_202602251340.csv` is a single-date-derived, retroactively-applied universe, not a proper monthly-reconstituted point-in-time universe. This is the biggest unresolved risk to the backtest's validity. | `mcap_based_universe_202602251340.csv`; universe logic wherever it filters this file down to Top-50 (not centralized — search per-notebook) |
| Wire PostgreSQL into the pipeline | **Not started** — confirmed zero references to `db_connections`/`postgres`/`sqlalchemy` anywhere in `files/`. | `Python_Scripts/db_connections.py` (module exists, unused) → target `files/data_loader.py` |
| Reconcile the HAR-RS claim | **Unresolved** — no notebook found implementing it; only the Phase-1 Word doc describes it. Either the notebook was never committed, was deleted, or the doc describes work done outside this repo. Worth asking around before assuming it's just "somewhere else in the repo." | `Volatility Research for AA smallcases.docx` (description only) |
| No automated test suite | Pipeline correctness is validated only by comparing output against `smoothed_signal.xlsx` (a 69-row, single-ticker snapshot) — an ad hoc check, not unit tests. | `files/output_writer.py`, `smoothed_signal.xlsx` |

### Research extensions worth exploring
| Extension | Description |
|---|---|
| Macro variable integration | FX, commodities, global equities, fixed income, PE/PB/Div yield across 7 market-cap + 18 sectoral indices — fully scoped as a to-do list in `Volatility Research for AA smallcases.docx`, but **not started in any notebook** (see corrected tiering, Section 8). |
| Gold modelling for the original Nifty/Gold AA smallcase | Still unresolved per the original research brief: Supertrend on Gold first (`Python_Scripts/ST.py::getSupertrend` already exists and could be reused), then the same linear-model framework used for Nifty. |
| Survivorship-bias-free backtesting | Currently relies on ad hoc Refinitiv CSV backfill for delisted tickers; a proper historical-constituents database with delisting dates would be more robust. |
| Extend signal to other geographies/indices | The MASS pipeline is ticker-agnostic — just needs price history in `INDTradingDays.xlsx` and a `config.py` entry. |
| Automate scheduled signal refresh | Once PostgreSQL is wired in, `main.py` can be scheduled (cron); `DbConnections` is already built to support this. |

---

## 11. Companion Documents

| Document | Purpose |
|---|---|
| **[`KT_LowVol_Strategy.docx`](KT_LowVol_Strategy.docx)** | The formal knowledge-transfer Word document — same verified content as this README, in the org's standard KT format. Use this if you need a document to hand off/print/share outside of git. |
| **[`Low_Vol_Strategy_Research_Report.docx`](Low_Vol_Strategy_Research_Report.docx)** | Management-facing performance report (March 2026). Cite this — and Section 6 of this README, which was cross-checked against it — for any number you need to use externally. |
| **[`Volatility Research for AA smallcases.docx`](Volatility%20Research%20for%20AA%20smallcases.docx)** | The original Phase-1 research brief and manager's notes ("Manu's points"). Contains the still-unresolved Gold-modelling task and the macro-variable EDA to-do list, and is the only surviving description of the HAR-RS model (see Section 10). |
| **[`Task_List.md`](Task_List.md)** | Chronological task log, June 2025–May 2026, with dated deliverables. |

---

## 12. Key Conventions

- Notebooks use `#%%` cell delimiters (Spyder/VS Code cell format).
- Signal-level filtering runs weekly (`freq='W'`); portfolio construction/rebalancing is monthly (first rebalance date of each calendar month). Signal export starts from `signal_start` (default `2020-01-01`).
- `windmillcheck_ALL.log` is the logging output from `QuantBacktester.py`.
- `~$`-prefixed files are Excel lock files — do not commit them.
- Database configs (`db_config.yaml`, `central_config_all.yaml`) are intentionally not in the repo — create them locally per `Python_Scripts/db_connections.py` if you take on the PostgreSQL integration task.
