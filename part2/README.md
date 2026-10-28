# Part 2 - Hands-on analysis of security-level data (2A-2D)

**Owner:** Member 2 ____

**Data:** Reads `data/raw/class project data (part 2 - factor portfolio construction).csv`, plus HML and MSCI USA from the FF/MSCI workbook.

Put your notebooks / scripts for this part in this folder. Save figures to `output/figures/` and tables to `output/tables/`, with the question number in the file name (e.g. `fig_2A_xxx.png`).

## Final deliverables and source code

- Final English report: `part2/documents/Part2_report.docx`.
- Final exhibit appendix, including Figures 2.1-2.8: `part2/documents/Part2_exhibits.docx`.
- Individual figures: `output/figures/`, with question-specific names such as `fig_2A_stock_counts.png`.
- Generated numerical tables: `output/tables/`.
- Analysis source: the six scripts in the execution sequence below, under `part2/python_source/`.
- Report and exhibit builder: `part2/python_source/build_consolidated.py`.

The approved minimal upload contains two Word documents, eight selected PNG figures, seven Python files, and three dependency files. Other generated diagnostics and intermediate files do not need to be uploaded. The documents folder contains only the two final Word documents; generated consolidation audit files are written to `part2/generated/consolidated/`.

## Python environment

Use **Python 3.12** and run the following commands from the **Git repository root**. Question 2A records the Git revision, so use a repository checkout rather than a folder copied without Git metadata.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r part2/python_source/requirements_consolidation.txt
```

Keep all three dependency files: `part2/python_source/requirements_consolidation.txt` includes `part2/python_source/requirements_2B.txt`, which includes `part2/python_source/requirements_2A.txt`. Installation requires access to the declared Python packages. Word rendering may vary with installed fonts and Office software; the documents use Arial.

## Reproduce Questions 2A-2D

Run these scripts in order after installing the dependencies:

```bash
python part2/python_source/question_2A.py
python part2/python_source/diagnostic_2A_pb_flag.py
python part2/python_source/question_2A5.py
python part2/python_source/question_2B.py
python part2/python_source/question_2C.py
python part2/python_source/question_2D.py
python part2/python_source/build_consolidated.py
```

The scripts use the professor-provided datasets already in `data/raw/` and the existing shared `src/config.py` and `src/utils.py`. Do not edit these shared inputs or utilities to run Part 2.

Question 2A generates the cleaned-return cache; the flag diagnostic generates its provisional-flag copy. Later scripts regenerate the required intermediate CSVs, holdings files, validation records, figures, and tables. The final builder reads those generated results and recreates the report and exhibit documents. No intermediate CSVs or cleaned-data caches need to be supplied separately if the full sequence is run.

**Rerunning scripts may overwrite their generated outputs**, including the final Word documents. Preserve any manual document edits separately or reproduce the work in a separate checkout.

The main 2B-2D analysis uses formation dates December 1998-November 2018 and investment returns January 1999-December 2018. It retains the provisional P/B flags and uses monthly 1st/99th-percentile winsorized stock returns. Original-return and flag-exclusion results remain sensitivity analyses. Returns are decimals internally; arithmetic annualized returns and geometric CAGR are reported separately.

## Outstanding team check

**Member 1's independent MSCI USA and Fama-French HML reconciliation remains pending.** Internal reference checks against the professor's workbook do not establish agreement with Member 1's separate calculations. The pending check does not prevent sharing this Part 2 package with the team.
