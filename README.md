# FE5108 Portfolio Theory and Investments — Class Project (Fall 2026)

Practitioner segment class project, NUS RMI.

- **Deadline:** Sunday, **8 Nov 2026**, submitted by email (PDF or Word; code as attachment or appendix)
- **Length:** max **8 pages** of text, excluding exhibits
- **Cover page:** state each member's contribution
- Assignment PDF and team plan: see [`Read it before you do!/`](Read%20it%20before%20you%20do!/)

---

## Team & division of work

Members are numbered **1–5** (Member 1 owns Part 1, etc.) to avoid confusion with question numbers like 1A, 2B.
Each member owns the **data loading, code, exhibits and write-up** of their own part.

| Member | Part | Points | Page budget | Data used |
|---|---|---|---|---|
| 1 ____ | Part 1 — Factor investing (1A–1E) | 22 | ~1.75 | FF/MSCI workbook (all 4 sheets) |
| 2 ____ | Part 2 — Security-level data (2A–2D) | 20 | ~1.5 | Part 2 CSV; HML + MSCI USA from FF/MSCI workbook |
| 3 ____ | Part 3 — Portfolio construction (3A–3E) | 21 | ~1.75 | Part 3 workbook; MSCI USA from FF/MSCI workbook |
| 4 ____ | Part 4 — to be released | ~18 | ~1.5 | TBD |
| 5 ____ | Part 5 — to be released | ~19 | ~1.5 | TBD (FF/MSCI workbook is labelled "parts 1 and 5") |

There are **no data hand-offs** between members: everyone reads what they need directly from `data/raw/`.

---

## Directory structure

```
Final Project/
├── README.md                  This file
├── .gitignore
├── requirements.txt           Python packages used
│
├── Read it before you do!/    Assignment PDF and team plan
│
├── data/
│   └── raw/                   Data provided by the professor — DO NOT EDIT
│       ├── class project data (FF MSCI) (parts 1 and 5).xlsx
│       ├── class project data (part 2 - factor portfolio construction).csv
│       └── class project data (part 3 - pf construction).xlsx
│
├── src/
│   └── utils.py               Shared helpers (annualization, Sharpe ratio)
│
├── part1/ … part5/            One folder per member: notebooks / scripts
│
├── output/
│   ├── figures/               e.g. fig_1C_sharpe.png
│   └── tables/                e.g. tab_3A_weights.csv
│
└── report/                    Write-up drafts and final report
```

---

## Data files

| File | Contents | Used by |
|---|---|---|
| `class project data (FF MSCI) (parts 1 and 5).xlsx` | 4 sheets: FF portfolios sorted on beta; FF portfolios sorted on prior return (momentum); FF 3-factor returns; MSCI factor total-return index levels (5 indexes) | Members 1, 2, 3 (and 5) |
| `class project data (part 2 - factor portfolio construction).csv` | Anonymized stock-level data: `stock_id, date, Pb, Bv, R1M_Usd, Vol3Y_Usd, Mkt_Cap_3M_Usd`; Nov 1998 – Mar 2019 | Member 2 |
| `class project data (part 3 - pf construction).xlsx` | FF 49 industry portfolios, value-weighted monthly returns, Jan 1995 – Jul 2023 | Member 3 |

### Things to watch out for when loading

- **FF beta portfolios:** in the header, the 8 columns between `Lo 10` and `Hi 10` were converted by Excel into dates (`2023-12-02` … `2023-12-09`). They are actually deciles 2–9. Data start in Jul 1963.
- **FF momentum & beta sheets:** several blocks are stacked in one sheet (VW monthly, EW monthly, annual, number of firms, …). Use only the **"Value Weighted Returns -- Monthly"** block.
- **FF 3 factors:** annual factors follow below the monthly block — don't read them in. Units are **percent** (divide by 100).
- **MSCI:** these are **index levels**, not returns — compute month-end to month-end % change. Numbers contain thousands separators (e.g. `1,182.011`). The series starts on 30 Dec 1994, so the first monthly return is Jan 1995.
- **Stock-level data:** percentile fields are on a **0–1** scale (the assignment says 0–100; same meaning). `R1M_Usd` is a **decimal, one-month-forward** return: the row dated 31 Dec 1998 is the return for Jan 1999. Shift by one month before comparing with MSCI/FF.
- **49 industries:** no `-99.99` missing values in Jan 1995 – Jul 2023. Units are percent.

### Cross-check

MSCI USA returns are computed separately by Members 1, 2 and 3, and HML is read separately by Members 1 and 2.
After loading, compare a few values in the group chat (e.g. MSCI USA and HML for Jan 1995) so the report stays consistent.
Members 1 and 2 should also align the wording on how HML is constructed (1A vs. 2C/2D).

---

## Team conventions

- **Units:** all returns in **decimals** (0.01 = 1%) inside code; convert to % only when displaying.
- **Dates:** month-end index (`to_period('M')` in pandas); each row = the return earned *in* that month.
- **Annualization:** agree on one method (return, volatility, Sharpe), implement it once in `src/utils.py`, and state it once in the report.
- **Exhibits:** every chart/table states what is shown, data source, time period and investable universe; all axes labelled; consistent fonts, colours and sizes.
- **File names:** include the question number, e.g. `fig_1C_sharpe.png`, `tab_3A_weights.csv`.

---

## Git workflow

- **Only edit your own folder** (`partN/`). Never edit `data/raw/`. Tell the group before changing `src/utils.py`.
- **Pull before you start, push when you finish a step.** Don't sit on changes for days.
- Notebooks (`.ipynb`) are hard to merge — only edit your own.

```bash
git clone https://github.com/WeekeyZhou/<repo-name>.git   # first time only
git pull                                                  # before you start working
git add part2/                                            # add your own folder
git commit -m "Part2: 2A winsorize + coverage plot"       # describe what you did
git push                                                  # upload
git status                                                # when unsure, check first
```

### Setup

```bash
pip install -r requirements.txt
```
