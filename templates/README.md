# KT templates

Two reusable templates for producing a project handover package (a README.md + a Word KT
document) in a new project, in the same style/rigor used for this one.

- **`README_TEMPLATE_PROMPT.md`** — a prompt to paste into a Claude Code session opened in the
  target project. Tells the agent how to research the project (read code + reports + result
  files, verify claims, flag reproducibility/data-quality gaps) and gives the exact section
  skeleton to follow.
- **`KT_DOC_TEMPLATE.py`** — a python-docx script skeleton for the Word KT document. Copy it
  into the target project, have the agent fill in the `{{PLACEHOLDER}}` fields with verified
  content (same research pass as the README), then run it to generate the `.docx`.

## Recommended workflow in a new project

1. Copy both files into the new project (or point an agent at them).
2. Ask the agent to research first — read all notebooks/scripts, all existing
   reports/docs, and any output/result files — and only then fill in the KT script's
   placeholders and write the README, per the two templates.
3. Explicitly ask it to flag, not silently repeat, any claim in an existing report that it
   could not verify against source code or result files. That cross-check is the main value of
   this whole exercise — it's what turns a KT doc from "what we think we did" into "what we can
   prove we did."
4. Run `python KT_DOC_TEMPLATE.py` (with dependencies `python-docx` installed) from the project
   root once filled in, and rename the output file.
