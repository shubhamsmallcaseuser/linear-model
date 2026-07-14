# Prompt template: generate a KT-style README.md for a research/analysis project

Paste this into a Claude Code session opened in the target project's root directory. Fill in
the `{{...}}` placeholders first (or just describe them in your own words — Claude can infer
most of it from the codebase).

---

## The prompt

I'm leaving this project/team and need a `README.md` that works as a **knowledge-transfer
document** for my successor — not a generic project blurb. Go through the codebase as an
expert {{DOMAIN ROLE, e.g. "quantitative researcher" / "data scientist" / "ML engineer"}}
and write it. Requirements:

1. **Read everything before writing anything.** Go through all notebooks/scripts, all
   design/report documents (Word docs, PDFs, wikis, slide decks — wherever findings were
   written up), and the actual output artifacts (result files, saved metrics, dashboards).
   Don't summarize from filenames or folder structure alone.

2. **Cross-check narrative claims against code and data, and say so explicitly.** Any
   Word/PDF report or prior KT doc makes claims about what was implemented, what won, and
   what the numbers are. For each major claim, verify it against the actual notebook/script
   that supposedly produced it, and against any raw output files (result spreadsheets, logs,
   metric dumps). If a notebook cited as "the source of X" doesn't actually contain the code
   for X, or if a headline number can't be traced to any script currently in the repo, **say
   so in the README** — don't just repeat the claim. This is the single most valuable thing
   the README can do for a successor: separate "verified against source" from "claimed but
   unverified."

3. **Flag data-quality and metric-definition traps you notice**, even if the original
   report/KT doc didn't mention them — e.g. a summary statistic distorted by one outlier fold,
   two same-named metrics (e.g. a raw R² vs. a model-specific R²) that are easy to confuse,
   broken/incomplete pipelines (failed hyperparameter search, TODOs left in code), etc.

4. **Write for someone who has zero context and needs to be productive in one sitting** — they
   should be able to read this once and know: what the project does, what actually works,
   what the best result is (and how much to trust it), which files to open first, and what's
   still broken or unfinished.

Use this section skeleton (adapt section names to the project's domain, drop sections that
genuinely don't apply, but don't skip the "verify claims / flag caveats" spirit of any of them):

```markdown
# {{Project Name}}

One paragraph: what this project does, for whom, and why it exists. State plainly that this
is a knowledge-transfer document for a successor.

## 1. What this project is
Goal, scope/universe, method/approach, in plain language a new reader can follow.

## 2. Headline result — and important caveats
State the best result / main conclusion plainly. Immediately follow with anything you found
during verification that undermines full confidence in it (missing source code, unreproducible
numbers, outlier-distorted stats, stale assumptions) — don't bury this in a footnote.

## 3. Core concepts (glossary)
A table of domain terms a newcomer needs (metrics, jargon, abbreviations used throughout the
code) — assume they know general {{domain}} but not this project's specific vocabulary.

## 4. Pipeline / methodology
Numbered steps of how raw input becomes a result: data loading, transforms, feature/label
construction, fitting/estimation, evaluation. Name the actual functions/files responsible for
each step (verified by reading the code, not the report).

## 5. Approaches / models / experiments tried
A table: each approach, what it added over the baseline, its status (confirmed implemented and
working / implemented but rejected / **claimed but source not found**), and which file
implements it. This is where reproducibility gaps get exposed most clearly.

## 6. Result numbers
Pull actual numbers from result files (not just narrative prose) where possible. Call out any
metric-naming confusion or statistically fragile summary values (outlier-driven means, etc.).

## 7. Repository structure
Table of top-level folders/files and what's in each.

## 8. Code/notebook reading guide
Tier the files: **must-read** (1-3 files that explain the "why" and the main "what"),
**read-if-extending** (secondary/appendix work), **skip** (superseded/scratch/historical). Say
why each tier is what it is.

## 9. Environment & how to run
Concrete setup commands, required data files, any path/config assumptions that aren't obvious.

## 10. Known gaps / pending work for the next owner
Ranked list: what's broken, what's missing, what's half-finished, and good next research
directions — separate "must fix to trust the headline result" from "nice-to-have extensions."
```

Style notes:
- Prefer tables over long prose wherever there's a natural row/column structure (file lists,
  glossary, model comparisons).
- Use `code formatting` for every file, function, and variable name so they're scannable.
- Keep an honest, plain tone — this document's whole value is trustworthiness, not polish.
- If you find and fix a factual error in an existing report/KT doc while researching, prefer
  fixing that source document directly over just noting the discrepancy in the README (ask the
  user first if it's not obvious which document is "the fix" vs. "the flag").
