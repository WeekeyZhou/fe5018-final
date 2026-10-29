"""Part 3 shared helpers (used by question_3B ... question_3E notebooks).

- load_industry_returns(): FF 49 industries, monthly DECIMAL returns, Period index
- load_weights_3A():       the three 3A portfolios (saved by question_3A.ipynb)
- portfolio_returns():     constant-weight portfolio returns r_p,t = w' r_t
- NAMES / EN / CN:         industry code -> English short label / Chinese name
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src import config, utils  # noqa: E402

# Column labels used in every Part 3 exhibit
COLS = {"mv_short": "Min-var (shorts allowed)",
        "mv_long_only": "Min-var (long-only)",
        "inverse_vol": "Inverse volatility"}
SHORT_LABELS = {"mv_short": "Min-var\n(shorts allowed)",
                "mv_long_only": "Min-var\n(long-only)",
                "inverse_vol": "Inverse\nvolatility"}
PF_COLORS = {"mv_short": config.COLORS[0],
             "mv_long_only": config.COLORS[1],
             "inverse_vol": config.COLORS[2]}

NAMES = {  # code: (English short label for exhibits, Chinese name)
    "Agric": ("Agriculture", "农业"), "Food": ("Food products", "食品"),
    "Soda": ("Candy & soda", "糖果与软饮"), "Beer": ("Beer & liquor", "啤酒与烈酒"),
    "Smoke": ("Tobacco", "烟草"), "Toys": ("Recreation", "休闲用品/玩具"),
    "Fun": ("Entertainment", "娱乐"), "Books": ("Printing & publishing", "印刷出版"),
    "Hshld": ("Consumer goods", "日用消费品"), "Clths": ("Apparel", "服装"),
    "Hlth": ("Healthcare services", "医疗服务"), "MedEq": ("Medical equipment", "医疗器械"),
    "Drugs": ("Pharmaceuticals", "制药"), "Chems": ("Chemicals", "化工"),
    "Rubbr": ("Rubber & plastics", "橡胶塑料"), "Txtls": ("Textiles", "纺织"),
    "BldMt": ("Construction materials", "建材"), "Cnstr": ("Construction", "建筑"),
    "Steel": ("Steel works", "钢铁"), "FabPr": ("Fabricated products", "金属制品"),
    "Mach": ("Machinery", "机械"), "ElcEq": ("Electrical equipment", "电气设备"),
    "Autos": ("Autos & trucks", "汽车与卡车"), "Aero": ("Aircraft", "飞机制造"),
    "Ships": ("Ships & rail equipment", "船舶与铁路设备"), "Guns": ("Defense", "国防军工"),
    "Gold": ("Precious metals", "贵金属"), "Mines": ("Non-precious mining", "非贵金属采矿"),
    "Coal": ("Coal", "煤炭"), "Oil": ("Petroleum & natural gas", "石油天然气"),
    "Util": ("Utilities", "公用事业"), "Telcm": ("Communication", "通信"),
    "PerSv": ("Personal services", "个人服务"), "BusSv": ("Business services", "商业服务"),
    "Hardw": ("Computer hardware", "计算机硬件"), "Softw": ("Computer software", "软件"),
    "Chips": ("Electronic equipment", "电子设备/芯片"), "LabEq": ("Measuring & control equip.", "测量与控制设备"),
    "Paper": ("Business supplies", "商业用品/纸业"), "Boxes": ("Shipping containers", "包装容器"),
    "Trans": ("Transportation", "交通运输"), "Whlsl": ("Wholesale", "批发"),
    "Rtail": ("Retail", "零售"), "Meals": ("Restaurants & hotels", "餐饮酒店"),
    "Banks": ("Banking", "银行"), "Insur": ("Insurance", "保险"),
    "RlEst": ("Real estate", "房地产"), "Fin": ("Trading", "金融交易"),
    "Other": ("Other", "其他"),
}
EN = {k: v[0] for k, v in NAMES.items()}
CN = {k: v[1] for k, v in NAMES.items()}

SOURCE_FF49 = ("Source: Kenneth French Data Library, 49 US industry portfolios "
               "(value-weighted, total returns).")


def load_industry_returns() -> pd.DataFrame:
    """FF 49 industry value-weighted monthly returns as decimals (Jan 1995 - Jul 2023).

    Same parsing as question_3A.ipynb: find the header row ('Agric' in column 2),
    keep the contiguous YYYYMM rows below it, strip trailing spaces in codes,
    check that no -99.99 / -999 missing values are present.
    """
    raw = pd.read_excel(config.FILE_PART3, header=None)
    hdr = raw.index[raw.iloc[:, 1].astype(str).str.strip().eq("Agric")][0]
    codes = raw.iloc[hdr, 1:].astype(str).str.strip().tolist()
    body = raw.iloc[hdr + 1:, :].copy()
    body.columns = ["month"] + codes
    is_month = body["month"].astype(str).str.strip().str.fullmatch(r"\d{6}(\.0)?").to_numpy()
    n_rows = len(is_month) if is_month.all() else int(np.argmin(is_month))
    body = body.iloc[:n_rows].set_index("month")
    ret_pct = utils.to_monthly_index(body.apply(pd.to_numeric))
    if ret_pct.isin([-99.99, -999]).any().any() or ret_pct.isna().any().any():
        raise ValueError("Missing values (-99.99 / -999 / NaN) found in industry returns")
    assert set(ret_pct.columns) == set(NAMES)
    return utils.pct_to_decimal(ret_pct)


def load_weights_3A() -> pd.DataFrame:
    """Weights saved by question_3A.ipynb (index = industry code, columns = COLS keys)."""
    path = HERE / "weights_3A.pkl"
    if not path.exists():
        raise FileNotFoundError("weights_3A.pkl not found - run question_3A.ipynb first")
    W = pd.read_pickle(path)
    assert np.allclose(W.sum(), 1.0), "3A weights do not sum to 1"
    return W


def portfolio_returns(rets: pd.DataFrame, W: pd.DataFrame) -> pd.DataFrame:
    """Constant-weight portfolio returns r_p,t = w' r_t (i.e. rebalanced monthly
    back to the fixed target weights, no re-estimation)."""
    return rets[W.index] @ W


def min_var_long_only(df: pd.DataFrame, tol: float = 1e-6) -> pd.Series:
    """Long-only, fully invested minimum-variance weights from the sample covariance of `df`.

    Same method as question_3A.ipynb (cvxpy / CLARABEL); weights below `tol` are set to 0
    and the rest re-normalized. Also checks the KKT optimality conditions.
    """
    import cvxpy as cp

    S = df.cov().to_numpy()
    n = S.shape[0]
    w = cp.Variable(n)
    prob = cp.Problem(cp.Minimize(cp.quad_form(w, cp.psd_wrap(S))), [cp.sum(w) == 1, w >= 0])
    prob.solve(solver=cp.CLARABEL)
    if prob.status != "optimal":
        raise RuntimeError(f"optimizer status: {prob.status}")
    x = np.where(w.value < tol, 0.0, w.value)
    x = x / x.sum()
    # KKT: held assets have equal marginal variance contribution; excluded assets a higher one
    mrc = S @ x / (x @ S @ x)
    assert np.allclose(mrc[x > 0], 1, atol=1e-3) and (mrc[x == 0] >= 1 - 1e-3).all(), "KKT check failed"
    return pd.Series(x, index=df.columns, name="mv_long_only")


MSCI_USA = "USA Standard (Large+Mid Cap)"


def load_msci_usa() -> pd.Series:
    """MSCI USA Standard (large+mid cap), gross total return, USD -> monthly decimal returns.

    Same logic as Part 2's loader: locate the 'Date' header row, read the contiguous
    monthly block (copyright text follows below), strip thousands separators, and
    convert month-end levels to month-end to month-end returns. First return = Jan 1995.
    """
    sheet = pd.read_excel(config.FILE_FF_MSCI, sheet_name=config.SHEET_MSCI, header=None)
    meta = {str(a).strip(): str(b).strip() for a, b in sheet.iloc[:6, :2].itertuples(index=False, name=None)}
    assert meta.get("Index Level :") == "Gross" and meta.get("Currency :") == "USD"
    h = int(np.flatnonzero(sheet.iloc[:, 0].astype(str).str.strip().eq("Date"))[0])
    j = int(np.flatnonzero(sheet.iloc[h].astype(str).str.strip().eq(MSCI_USA))[0])
    end = h + 1
    while end < len(sheet) and pd.notna(sheet.iat[end, 0]):
        end += 1
    block = sheet.iloc[h + 1:end, [0, j]]
    levels = pd.Series(
        pd.to_numeric(block.iloc[:, 1].astype(str).str.replace(",", "", regex=False)).to_numpy(),
        index=pd.to_datetime(block.iloc[:, 0].astype(str).str.strip(), format="%b %d, %Y"))
    levels = utils.to_monthly_index(levels)
    assert levels.index.is_unique and (levels > 0).all()
    return utils.levels_to_returns(levels).rename("MSCI USA")


def light_hex(color: str, strength: float = 0.30) -> str:
    """Light tint of a colour as 'RRGGBB' (same tint as the 3A table: 30% colour, 70% white)."""
    import matplotlib.colors as mcolors
    rgb = strength * np.array(mcolors.to_rgb(color)) + (1 - strength)
    return mcolors.to_hex(rgb).lstrip("#").upper()
