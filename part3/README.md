# Part 3 - Portfolio construction (3A-3E)

**Owner:** Member 3 Zhou Mo (Weekey)

**Data:** Reads `data/raw/class project data (part 3 - pf construction).xlsx` (FF 49 industries, value-weighted, monthly, Jan 1995 - Jul 2023), plus MSCI USA from the FF/MSCI workbook (3E only).

## Final deliverables and source code

- Final English report: `part3/documents/Part3_report.docx` (about 900 words of body text).
- Final exhibit appendix, Tables 3.1-3.9 and Figures 3.1-3.8: `part3/documents/Part3_exhibits.docx`.
- Individual figures: `output/figures/fig_3*.png`; numerical tables: `output/tables/tab_3*.csv` (3A also as a colour-coded `.xlsx`).
- Analysis notebooks (Chinese notes for the team, English exhibits): `part3/python_source/question_3A.ipynb` ... `question_3E.ipynb`.
- Shared Part 3 helpers (data loading, MSCI loader, long-only optimizer): `part3/python_source/part3_common.py`.
- Report and exhibit builder: `part3/python_source/build_part3_docs.py`.

## Reproduce Questions 3A-3E

Install `requirements.txt` (needs `cvxpy` and `python-docx`), then run the notebooks **in order** (3B-3E read the weights that 3A saves in `weights_3A.pkl`), then the builder:

```bash
jupyter nbconvert --to notebook --execute --inplace part3/python_source/question_3A.ipynb
jupyter nbconvert --to notebook --execute --inplace part3/python_source/question_3B.ipynb
jupyter nbconvert --to notebook --execute --inplace part3/python_source/question_3C.ipynb
jupyter nbconvert --to notebook --execute --inplace part3/python_source/question_3D.ipynb
jupyter nbconvert --to notebook --execute --inplace part3/python_source/question_3E.ipynb
python part3/python_source/build_part3_docs.py
```

**Rerunning the builder overwrites both Word files.** Keep manual document edits in a separate copy.

Conventions: returns in decimals; weights fixed at 31 Dec 2004 (3D: 31 Dec 2015) and rebalanced monthly to target; volatility = sample std of monthly returns x sqrt(12). `SHOW_REFERENCE` in 3B-3D switches the equal-weight / single-industry reference rows on or off.

## Cross-check for the team

MSCI USA (Standard, gross, USD) January 1995 monthly return = **2.7810%** (Part 3 loader). Members 1 and 2 should obtain the same value.
