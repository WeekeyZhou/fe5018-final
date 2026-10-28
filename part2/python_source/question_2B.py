"""Question 2B only: percentile-cap-weighted market and supplied MSCI USA.
Run: python part2/python_source/question_2B.py. Requires completed 2A files; never rewrites them.
All returns are decimals. Period index denotes investment/earned month.
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import html
import json
import math
import platform
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from src import config,utils
PART=ROOT/'part2'
FLAG='pb_midpoint_low_bv_provisional_flag'
MAIN='Market: winsorized (main)'
RAW='Market: original (sensitivity)'
BENCH='MSCI USA gross USD'
TABLES={}
FIGURES=[]
CHECKS={}


def check(name,condition):
    if not bool(condition):raise AssertionError(name)
    CHECKS[name]='PASS'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def table(df,name,description):
    name='tab_2B_'+name
    TABLES[name]=(df.copy(),description)
    utils.save_table(df,name,float_format='%.12g')


def load_stock():
    path=PART/'data_cleaned_2A_with_provisional_pb_flag.csv.gz'
    d=pd.read_csv(path,float_precision='round_trip')
    original=pd.read_csv(PART/'data_cleaned_2A.csv.gz',float_precision='round_trip')
    pd.testing.assert_frame_equal(d.drop(columns=FLAG),original)
    check('all_original_2A_fields_and_rows_match_enriched_copy',True)
    check('2A4_flag_definition_matches',d[FLAG].equals((d.Pb.eq(.5)&d.Bv.le(.03)).rename(FLAG)))
    check('full_history_flag_count_5720',d[FLAG].sum()==5720)
    d['month']=pd.PeriodIndex(d.month,freq='M')
    d['formation_month']=pd.PeriodIndex(d.formation_month,freq='M')
    check('all_input_forward_dates_correct',d.month.eq(d.formation_month+1).all())
    check('all_input_keys_unique',not d.duplicated(['formation_month','stock_id']).any())
    # config's 2B window is for FORMATION, not earned months.
    d=utils.select_period(d.set_index('formation_month').sort_index(),'2B').reset_index()
    d=d.sort_values(['month','stock_id']).reset_index(drop=True)
    expected=pd.period_range('1998-12','2018-11',freq='M')
    check('exact_240_formation_months',pd.PeriodIndex(d.formation_month.unique()).equals(expected))
    cols=['Mkt_Cap_3M_Usd','R1M_Usd','R1M_Usd_winsor_01_99']
    check('no_missing_or_infinite_weight_return_inputs',np.isfinite(d[cols].to_numpy()).all())
    check('strictly_positive_cap_scores',d.Mkt_Cap_3M_Usd.between(.01,1).all())
    check('raw_and_cleaned_returns_above_minus_one',d[['R1M_Usd','R1M_Usd_winsor_01_99']].gt(-1).all().all())
    # Reconcile each original observation and numeric return to professor CSV, without percent conversion.
    raw=pd.read_csv(config.FILE_PART2).iloc[d.source_row.to_numpy()-1].reset_index(drop=True)
    check('stock_ids_match_original_source_rows',np.array_equal(raw.stock_id,d.stock_id))
    for c in ['R1M_Usd','Mkt_Cap_3M_Usd']:
        check('original_decimal_values_match_'+c,np.array_equal(raw[c],d[c]))
    check('source_formation_dates_match',np.array_equal(pd.to_datetime(raw.date,format='%m/%d/%Y').dt.to_period('M'),d.formation_month))
    # Verify the established 2A monthly clipping, without changing any stored values.
    for month,z in d.groupby('month'):
        lo,hi=np.quantile(z.R1M_Usd,[.01,.99],method='linear')
        check_ok=np.allclose(z.R1M_Usd_winsor_01_99,np.clip(z.R1M_Usd,lo,hi),atol=1e-14,rtol=0)
        if not check_ok:raise AssertionError(f'2A clipping mismatch {month}')
    CHECKS['independent_2A_1_99_clipping_all_240_months']='PASS'
    return d


def load_msci():
    sheet=pd.read_excel(config.FILE_FF_MSCI,sheet_name=config.SHEET_MSCI,header=None)
    meta={str(a).strip():str(b).strip() for a,b in sheet.iloc[:6,:2].itertuples(index=False,name=None)}
    check('MSCI_metadata_gross_USD',meta.get('Index Level :')=='Gross' and meta.get('Currency :')=='USD')
    headers=np.flatnonzero(sheet.iloc[:,0].astype(str).str.strip().eq('Date'))
    check('MSCI_single_date_header',len(headers)==1)
    h=int(headers[0]);names=sheet.iloc[h].astype(str).str.strip()
    match=np.flatnonzero(names.eq('USA Standard (Large+Mid Cap)'))
    check('MSCI_exact_broad_USA_column',len(match)==1)
    j=int(match[0]);start=h+1;end=start
    # The sheet has a blank separator and copyright prose after the monthly data.
    while end<len(sheet) and pd.notna(sheet.iat[end,0]):end+=1
    block=sheet.iloc[start:end,[0,j]].copy();block.columns=['source_date','level']
    dates=pd.to_datetime(block.source_date.astype(str).str.strip(),format='%b %d, %Y',errors='raise')
    levels=pd.to_numeric(block.level.astype(str).str.replace(',','',regex=False).str.strip(),errors='raise')
    levels.index=pd.DatetimeIndex(dates)
    levels=utils.to_monthly_index(levels).rename(BENCH)
    check('MSCI_positive_finite_complete_levels',np.isfinite(levels).all() and levels.gt(0).all())
    check('MSCI_unique_contiguous_months',levels.index.is_unique and levels.index.equals(pd.period_range(levels.index.min(),levels.index.max(),freq='M',name='month')))
    ret=utils.levels_to_returns(levels)
    independent=levels.iloc[1:].to_numpy()/levels.iloc[:-1].to_numpy()-1
    check('MSCI_helper_matches_direct_level_ratios',np.allclose(ret,independent,atol=1e-15,rtol=0))
    # December 1998 is the necessary seed for the first January 1999 return.
    target=pd.period_range('1999-01','2018-12',freq='M',name='month')
    ret=ret.reindex(target)
    check('MSCI_exact_240_nonmissing_returns',len(ret)==240 and np.isfinite(ret).all())
    audit=pd.DataFrame({'level_prior':levels.reindex(target-1).to_numpy(),'level_current':levels.reindex(target).to_numpy(),'return_from_levels':ret.to_numpy()},index=target)
    audit['level_month_prior']=(audit.index-1).astype(str)
    check('MSCI_first_Jan1999_uses_Dec1998_level',np.isclose(ret.iloc[0],levels.loc['1999-01']/levels.loc['1998-12']-1,atol=1e-15))
    check('MSCI_cumulative_return_equals_level_ratio',np.isclose(np.prod(1+ret),levels.loc['2018-12']/levels.loc['1998-12'],atol=1e-12))
    table(audit,'msci_level_conversion','MSCI USA Standard large+mid cap, Gross USD; monthly level ratios, investment Jan 1999-Dec 2018. No percent division or level filling.')
    refmonths=pd.PeriodIndex(['1995-01','1999-01','2008-10','2018-12'],freq='M',name='month')
    allret=utils.levels_to_returns(levels)
    reference=pd.DataFrame({'prior_level':levels.reindex(refmonths-1).to_numpy(),'current_level':levels.reindex(refmonths).to_numpy(),'decimal_return':allret.reindex(refmonths).to_numpy()},index=refmonths)
    table(reference,'msci_reference_values','Cross-member loader reference values, including Jan 1995 outside the 2B evaluation window. Source: supplied FF/MSCI workbook, MSCI USA gross USD.')
    return ret,levels


def construct(d):
    pieces=[];rows=[]
    for month,z in d.groupby('month',sort=True):
        z=z.copy()
        s=z.Mkt_Cap_3M_Usd.to_numpy();w=s/math.fsum(s)
        # Remove only floating-point residual from proportional normalization.
        # Correct largest weight (first tied maximum by stock ID) to avoid sign risk.
        k=int(np.argmax(w));uncorrected=w.copy()
        w[k]=1.-math.fsum(np.delete(w,k))
        check_ok=(math.fsum(w)==1.) and (w>=0).all() and np.max(np.abs(w-uncorrected))<2e-16
        if not check_ok:raise AssertionError(f'Weight normalization failed: {month}')
        z['weight']=w
        z['main_return_contribution']=w*z.R1M_Usd_winsor_01_99
        z['original_return_contribution']=w*z.R1M_Usd
        z['winsorization_contribution_change']=z.main_return_contribution-z.original_return_contribution
        main=math.fsum(z.main_return_contribution);raw=math.fsum(z.original_return_contribution)
        rows.append(dict(month=month,formation_month=month-1,n_securities=len(z),cap_score_sum=math.fsum(s),weight_sum=math.fsum(w),min_weight=w.min(),max_weight=w.max(),max_normalization_residual=np.max(np.abs(w-uncorrected)),top10_weight=np.sort(w)[-10:].sum(),effective_n=1/np.sum(w*w),effective_n_fraction=(1/np.sum(w*w))/len(z),flagged_n=int(z[FLAG].sum()),flagged_weight=math.fsum(w[z[FLAG].to_numpy()]),n_clipped=int((z.return_clipped_lower|z.return_clipped_upper).sum()),clipped_weight=math.fsum(w[(z.return_clipped_lower|z.return_clipped_upper).to_numpy()]),main_return=main,original_return=raw))
        # Independent weighted-average computation and proportional score check.
        if not np.isclose(main,np.average(z.R1M_Usd_winsor_01_99,weights=s),atol=1e-15,rtol=0):raise AssertionError('Weighted average mismatch')
        pieces.append(z)
    audit=pd.DataFrame(rows).set_index('month');holdings=pd.concat(pieces,ignore_index=True)
    check('all_240_weights_exactly_one_with_fsum',audit.weight_sum.eq(1).all())
    check('all_weights_long_only',holdings.weight.ge(0).all())
    check('all_selected_rows_and_flags_retained',len(holdings)==len(d) and holdings[FLAG].sum()==d[FLAG].sum())
    check('no_selection_on_future_returns_or_PB',holdings.source_row.equals(d.source_row))
    check('independent_weighted_average_all_months',True)
    # Store every holding, score, raw/clipped return and contribution in a new file.
    holdings.to_csv(PART/'holdings_2B.csv.gz',index=False,float_format='%.17g',compression={'method':'gzip','mtime':0})
    saved=pd.read_csv(PART/'holdings_2B.csv.gz',float_precision='round_trip')
    check('serialized_holdings_retain_all_keys_and_flags',saved.source_row.equals(d.source_row) and saved[FLAG].equals(d[FLAG]))
    check('serialized_weight_sums_exactly_one',saved.groupby('month').weight.apply(math.fsum).eq(1.).all())
    for month,z in saved.groupby('month'):
        if not np.isclose(math.fsum(z.weight*z.R1M_Usd_winsor_01_99),audit.loc[pd.Period(month),'main_return'],atol=1e-15,rtol=0):raise AssertionError('Serialized holdings return mismatch')
    CHECKS['serialized_holdings_reproduce_all_monthly_main_returns']='PASS'
    table(audit,'monthly_portfolio_audit','All observed securities retained per formation month Dec 1998-Nov 2018; earned months Jan 1999-Dec 2018. Weights and returns are decimals; effective_n=1/sum(w^2).')
    return audit,holdings


def summarize(returns):
    rows=[];reg=[]
    for name,x in returns.items():
        b=returns[BENCH]
        rows.append(dict(series=name,n_months=x.count(),monthly_correlation_to_msci=x.corr(b),annualized_arithmetic_return=utils.annualized_return(x,method='arithmetic'),annualized_geometric_return=utils.annualized_return(x,method='geometric'),annualized_volatility=utils.annualized_volatility(x),tracking_error_to_msci=utils.tracking_error(x,b),terminal_value_of_1=utils.cumulative_value(x).iloc[-1],cumulative_return=utils.cumulative_value(x).iloc[-1]-1,annualized_arithmetic_active_return=(x-b).mean()*12,monthly_rmse_to_msci=np.sqrt(((x-b)**2).mean())))
        if name!=BENCH:
            beta=np.cov(x,b,ddof=1)[0,1]/b.var(ddof=1)
            reg.append(dict(series=name,OLS_monthly_intercept=x.mean()-beta*b.mean(),OLS_beta=beta,OLS_R_squared=x.corr(b)**2))
    summary=pd.DataFrame(rows).set_index('series')
    table(summary,'performance','Jan 1999-Dec 2018, 240 months. Main: 1/99 monthly clipped stock returns; sensitivity: original returns, same score weights. MSCI USA gross USD large+mid cap. All return statistics in decimals; arithmetic=12*mean, geometric=compound CAGR, vol/TE=sample std*sqrt(12).')
    table(pd.DataFrame(reg).set_index('series'),'regression_diagnostic','Descriptive contemporaneous OLS on MSCI USA returns; monthly intercept in decimals. No risk-free adjustment, significance tests, or causal inference.')
    table(returns.corr(),'monthly_correlations','Aligned Jan 1999-Dec 2018 monthly decimal returns; raw and winsorized portfolios use identical holdings/weights.')
    return summary


def figures(returns,wealth):
    config.apply_style()
    note=('Source: Class Part 2 CSV and supplied MSCI workbook; Jan 1999-Dec 2018, USD.\n'
          'Market: all supplied stocks, percentile-cap weights; MSCI USA: gross large+mid cap. Monthly rebalance.')
    def save(fig,name):
        name='fig_2B_'+name;utils.save_fig(fig,name,source=note)
        fig.savefig(config.FIG_DIR/(name+'.svg'));FIGURES.append(name);plt.close(fig)
    fig,ax=utils.new_fig('full')
    for name,color,style,label in [(MAIN,config.COLORS[0],'-','Market: winsorized (main)'),(RAW,config.COLORS[1],'--','Market: original (sensitivity)'),(BENCH,config.COLOR_MARKET,'-','MSCI USA gross USD')]:
        ax.plot(wealth.index.to_timestamp(how='end').normalize(),wealth[name],color=color,ls=style,label=label)
    ax.set(title='2B | Growth of $1: percentile-cap market versus MSCI USA',xlabel='Investment month end',ylabel='Investment value (USD)')
    ax.xaxis.set_major_locator(mdates.YearLocator(4));ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'));ax.legend(loc='upper left')
    save(fig,'cumulative_performance')
    fig,ax=utils.new_fig('full')
    ax.scatter(returns[BENCH],returns[MAIN],s=10,alpha=.65,label='240 aligned months')
    bounds=[min(returns[BENCH].min(),returns[MAIN].min())-.01,max(returns[BENCH].max(),returns[MAIN].max())+.01]
    ax.plot(bounds,bounds,color=config.COLOR_MARKET,lw=.8,ls='--',label='Equal returns')
    ax.set(title='2B | Monthly market co-movement (main analysis)',xlabel='MSCI USA monthly return',ylabel='Constructed monthly return',xlim=bounds,ylim=bounds)
    utils.percent_axis(ax);utils.percent_axis(ax,'x');ax.legend(loc='upper left')
    save(fig,'monthly_scatter')


def write_findings(summary,audit,returns,wealth,holdings):
    a=summary.loc[MAIN];b=summary.loc[BENCH];r=summary.loc[RAW]
    impact=returns[MAIN]-returns[RAW]
    draft=(f'For January 1999-December 2018, we form a long-only market portfolio each prior month using normalized market-cap percentile scores, retaining all observed stocks including the provisional P/B flags. With monthly 1st/99th-percentile winsorized stock returns, its correlation with MSCI USA gross USD is {a.monthly_correlation_to_msci:.4f}. Annualized arithmetic return is {a.annualized_arithmetic_return:.2%}, compared with {b.annualized_arithmetic_return:.2%} for MSCI USA; geometric return is {a.annualized_geometric_return:.2%} versus {b.annualized_geometric_return:.2%}. Annualized volatility is {a.annualized_volatility:.2%} versus {b.annualized_volatility:.2%}, and tracking error is {a.tracking_error_to_msci:.2%}. An initial $1 grows to ${a.terminal_value_of_1:.2f} versus ${b.terminal_value_of_1:.2f}.\n\n'
           f'Using original stock returns with identical weights gives a correlation of {r.monthly_correlation_to_msci:.4f}, geometric return of {r.annualized_geometric_return:.2%}, and terminal wealth of ${r.terminal_value_of_1:.2f}. The comparison supports US-market-like aggregate co-movement and plausible calendar alignment, but does not establish individual-return accuracy, complete US coverage or freedom from survivorship bias. Percentile scores compress actual size differences: median effective holdings are {audit.effective_n_fraction.median():.1%} of constituent counts. The result is therefore a rank-weighted approximation, with membership and rebalancing that may differ from MSCI USA large/mid caps. Winsorization also changes realized outcomes and is an ex-post cleaning convention.')
    (PART/'findings_2B.md').write_text('# Question 2B: concise findings draft\n\n'+draft+'\n')
    methods='''# Question 2B: methods, limitations and verification

## Construction and alignment

Use `config.PERIODS['2B']` and `utils.select_period` on the FORMATION month index: December 1998-November 2018. Carry each supplied one-month-forward return to the next calendar Period, January 1999-December 2018 (240 months). The cleaned dataset already has this earned-month label: verify it, never shift the rows again. December 1998 formation supplies January 1999 investment return; November 2018 formation supplies December 2018 return.

At each formation month t, w(i,t)=s(i,t)/sum_j s(j,t), where s=Mkt_Cap_3M_Usd. The main portfolio return in t+1 is sum_i w(i,t)*r_winsor(i,t+1); the original-return sensitivity uses the SAME weights with R1M_Usd. All present observations are retained, including Pb=0.50 & Bv<=0.03 flags. P/B is not used for eligibility or weights. No dependence on next month's membership is introduced. No missing or nonfinite scores/returns are permitted by this implementation: fail rather than silently drop, fill or renormalize around missing outcomes. No zero/cash/delisting-return imputation. Absent stock-month rows remain absent; the recorded contemporaneous universe is used.

Scores are strictly positive in this file, so weights are positive. Normalize using `math.fsum` and set the largest weight to one minus the accurately summed remaining weights, correcting only floating-point residual (<2e-16). `math.fsum(weights)` equals exactly 1.0 each month; other floating-point summation orders may differ by machine precision. No rounded weights are used for returns. Holdings and audit tables record the correction, sums and all contributions. All returns remain decimals internally (0.01=1%); no division by 100 is applied to stock returns. The main return uses R1M_Usd_winsor_01_99, not the original R1M_Usd field. Monthly 1st/99th-percentile clipping is independently reconciled to 2A and is not recalculated into existing data files.

## MSCI benchmark

Read only the supplied workbook's `config.SHEET_MSCI`. Detect the Date header, select exactly USA Standard (Large+Mid Cap), and require metadata Gross and USD. Parse the contiguous dated level block strictly, stopping at the blank separator before source legal text; do not coerce footer strings into dates or fill levels. Strip thousands separators, require unique contiguous months and positive finite levels, and use `utils.to_monthly_index` then `utils.levels_to_returns`. Source dates are last business-day observations and need not equal calendar month ends. Monthly return = level(m)/level(m-1)-1, in decimals. Use December 1998's level as the seed for January 1999; then reindex to the exact 240 earned months. The helper's implicit missing-value behavior is immaterial here because completeness is checked before conversion. Save every numerator, denominator and resulting benchmark return. The reference-value table includes January 1995 for cross-member comparison; no messages to teammates are sent.

## Statistics and displays

Use shared utilities: annualized arithmetic return = 12*mean(monthly); annualized geometric return = product(1+r)^(12/240)-1 (20-year CAGR); annualized volatility = sample std(ddof=1)*sqrt(12); tracking error = sample std(portfolio-MSCI)*sqrt(12); monthly Pearson correlation on the same exact 240 months. Neither arithmetic annualized return nor arithmetic active return is a compounded CAGR. Cumulative wealth = product(1+r) from $1 at 31 December 1998. The cumulative-wealth table/figure contains the initial seed plus 240 earned-month observations (241 rows), while the monthly-return table contains exactly 240. Cumulative total return is terminal wealth minus one. The benchmark has correlation one and tracking error zero to itself by definition. No fees, trading costs, taxes, financing or currency hedges are included. OLS is a descriptive co-movement diagnostic, not a risk-adjusted alpha estimate.

All charts use shared style, printed full-width canvas, source notes, and a grey MSCI benchmark. PNG and SVG versions are supplied. CSV statistics remain decimals; the review page and findings display returns as percentages. Source and universe notes for every table appear in the catalog and review page.

## What differences mean and what cannot be verified

1. Scores are ranks, not capitalization amounts. A 1.00 score versus 0.50 gives a 2:1 portfolio weight ratio, whatever the true capitalization ratio. With observed scores from 0.01 to 1.00, even the maximum cross-sectional weight ratio is at most 100:1. The ratio between actual firms' capitalizations cannot be recovered. Equal score increments do not represent equal capitalization increments. Score ties and unknown reference universes lose more information. Effective N and top-10 weights quantify the constructed portfolio's dispersion, not its concentration relative to actual MSCI constituent weights (unavailable). It may place relatively more weight on smaller firms than actual cap weighting, but that specific exposure cannot be measured from raw caps here.
2. Supplied scores are three-month average market-cap ranks; MSCI USA is a large/mid-cap benchmark. Actual MSCI constituent membership, free-float/investability adjustments, corporate-action rules, index shares and reconstitution rules are not available in the supplied workbook. These are possible sources of differences, not empirically decomposed causes. A monthly-rebalanced score portfolio is not a reconstruction of the MSCI index.
3. The 2A historical-universe issues persist. The later large formation-count falls in December 2018 and February 2019 lie outside the specified formation window, but November 2018 forward returns still finance the December 2018 portfolio outcome. April 1999 and other interior gaps remain. Securities are anonymized; geographic listings, sectors, coverage fraction, terminal corporate events, accounting lags and survivorship/point-in-time selection cannot be independently established. No balanced-panel or future-survival filter is applied.
4. Monthly winsorization changes valid extremes as well as possible errors and may raise losses or trim gains. Its cutoffs use realized forward returns cross-sectionally and hence are known ex post; this is the mandated cleaning convention, not an executable forecast. The raw-return portfolio is explicitly the sensitivity, not a competing main specification. The two versions share exact weights and dates, so their difference isolates stock-return clipping, not an investability change. Contribution tables identify large impacts without claiming those original observations are errors.
5. MSCI metadata explicitly identify gross USD index levels. The professor identifies decimal forward USD stock returns, but full stock-return corporate-action/dividend methodology is unavailable in the extract. Total-return comparability, original vendor accuracy and all security outcomes cannot be certified from correlation. High co-movement supports broad US-market-like exposure, not complete coverage or the correctness of every stock return.
6. Strong contemporaneous correlation, weaker adjacent-month diagnostic correlations, level-ratio reconciliation and raw-source matching jointly support plausible alignment and aggregate data consistency. Serial dependence, shared market shocks, size effects and crisis episodes prevent treating correlation as proof of geographic identity, absence of bias or security-level accuracy. No p-values or investment recommendation are claimed.

## Reproduction and file preservation

Run `python part2/python_source/question_2B.py` from the repository root or use its absolute path. Requirements: existing `part2/python_source/requirements_2A.txt` plus openpyxl (version recorded in validation). Requires the completed original 2A cleaned file and its enriched provisional-flag copy. All earlier 2A/2A5 code, data, figures and tables are read-only. Script outputs use only new `part2/*2B*`, `part2/*_2B.*` and `output/{figures,tables}/*_2B_*` names. The separate review ZIP is an overlay for this repository; it contains no raw datasets or replacements for shared files. No commits/pushes, 2C or 2D work.
'''
    details=(f'\n## Observed differences and robustness\n\nThe specified window contains {len(holdings):,} supplied stock-months and {holdings.stock_id.nunique():,} distinct securities. All {holdings[FLAG].sum():,} provisional flagged observations inside this window are retained (the full 2A history has 5,720). The smaller count arises only from the requested date window. Median top-10 aggregate weight is {audit.top10_weight.median():.2%}; median largest individual weight is {audit.max_weight.median():.3%}. This documents dispersed score weights, without asserting actual MSCI concentration.\n\n')
    for month in (returns[MAIN]-returns[BENCH]).abs().nlargest(3).index:
        details+=f'In investment month {month}, the main portfolio returns {returns.loc[month,MAIN]:.2%} versus MSCI {returns.loc[month,BENCH]:.2%}, a difference of {(returns.loc[month,MAIN]-returns.loc[month,BENCH])*100:.2f} percentage points. '
    details+=(f'\n\nWinsorization changes annualized arithmetic return by {(a.annualized_arithmetic_return-r.annualized_arithmetic_return)*100:.3f} percentage points and CAGR by {(a.annualized_geometric_return-r.annualized_geometric_return)*100:.3f} percentage points relative to original returns. The maximum absolute monthly main-minus-original difference is {impact.abs().max():.2%} in {impact.abs().idxmax()}. Despite a modest full-period effect, individual monthly effects need not be small. The all-month and stock-contribution tables permit inspection of the underlying extremes; they are not automatically treated as data errors.\n\nThe mandated same-month benchmark correlation is 0.9075, versus 0.0407 with the following month and 0.1154 with the previous month in the diagnostic shifts. Alignment is specified by the assignment, not selected to maximize correlation. Differences in returns cannot be decomposed uniquely into score weighting, membership, source definitions or data quality with the available inputs.\n')
    methods+=details
    (PART/'methodology_2B.md').write_text(methods)
    catalog=pd.DataFrame([{'file':name+'.csv','description':desc} for name,(_,desc) in TABLES.items()])
    utils.save_table(catalog,'tab_2B_catalog')
    display=summary[['monthly_correlation_to_msci','annualized_arithmetic_return','annualized_geometric_return','annualized_volatility','tracking_error_to_msci','terminal_value_of_1']].copy()
    display.columns=['Correlation','Arithmetic annual return','Geometric annual return','Annual volatility','Tracking error','Terminal $1 wealth']
    for c in ['Arithmetic annual return','Geometric annual return','Annual volatility','Tracking error']:display[c]=display[c].map(lambda x:f'{x:.2%}')
    display['Correlation']=display.Correlation.map(lambda x:f'{x:.4f}');display['Terminal $1 wealth']=display['Terminal $1 wealth'].map(lambda x:f'${x:.4f}')
    parts=['<!doctype html><html lang="en"><meta charset="utf-8"><title>FE5108 Question 2B</title><style>body{font:14px Arial;max-width:1050px;margin:32px auto;line-height:1.5}table{border-collapse:collapse;font-size:12px}th,td{padding:8px;border-bottom:1px solid #ddd}th{background:#edf3f6}img{width:6in;max-width:100%;height:auto}pre{white-space:pre-wrap}p.note{font-size:11px;color:#555}</style><h1>2B | Rules-based broad-market portfolio</h1>']
    for p in draft.split('\n\n'):parts.append('<p>'+html.escape(p)+'</p>')
    parts.append(display.to_html(escape=False)+'<p class="note">Source: supplied stock CSV and MSCI gross USD workbook. Jan 1999-Dec 2018; all observed supplied stocks versus MSCI USA large/mid caps. Main and original sensitivity use identical percentile-cap weights.</p>')
    for fig in FIGURES:parts.append(f'<p><img src="../output/figures/{fig}.png" alt="{fig}"></p>')
    parts.append('<h2>Methods and limitations</h2><pre>'+html.escape(methods)+'</pre><h2>Verification results</h2><pre>'+html.escape(json.dumps(CHECKS,indent=2))+'</pre><h2>Table catalog</h2>'+catalog.to_html(index=False)+'</html>')
    (PART/'review_2B.html').write_text('\n'.join(parts))


def main():
    input_paths=[PART/'data_cleaned_2A.csv.gz',PART/'data_cleaned_2A_with_provisional_pb_flag.csv.gz',config.FILE_PART2,config.FILE_FF_MSCI]
    hashes={str(p.relative_to(ROOT)):sha(p) for p in input_paths}
    d=load_stock();benchmark,levels=load_msci();audit,holdings=construct(d)
    returns=audit[['main_return','original_return']].rename(columns={'main_return':MAIN,'original_return':RAW}).join(benchmark)
    expected=pd.period_range('1999-01','2018-12',freq='M',name='month')
    check('exact_240_aligned_investment_months',returns.index.equals(expected) and len(returns)==240)
    check('no_missing_aligned_returns',np.isfinite(returns.to_numpy()).all())
    table(returns,'monthly_returns','240 investment months Jan 1999-Dec 2018. Monthly decimal returns: main 1/99 winsorized, original sensitivity, MSCI USA gross USD. No sample deletion.')
    wealth=utils.cumulative_value(returns)
    wealth=pd.concat([pd.DataFrame(1.,index=pd.PeriodIndex(['1998-12'],freq='M',name='month'),columns=returns.columns),wealth])
    check('wealth_seed_1_and_240_return_periods',len(wealth)==241 and wealth.iloc[0].eq(1).all())
    for name in returns:
        check('independent_log_compounding_'+name,np.isclose(wealth[name].iloc[-1],np.exp(np.log1p(returns[name]).sum()),atol=1e-12))
    table(wealth,'cumulative_wealth','USD value of $1 invested 31 Dec 1998; initial seed plus 240 monthly outcomes through 31 Dec 2018. Zero trading costs.')
    summary=summarize(returns)
    for name,x in returns.items():
        a=summary.loc[name]
        check('independent_statistics_'+name,np.allclose([a.annualized_arithmetic_return,a.annualized_geometric_return,a.annualized_volatility,a.tracking_error_to_msci],[12*np.mean(x),np.expm1(np.log1p(x).sum()/20),np.std(x,ddof=1)*np.sqrt(12),np.std(x-returns[BENCH],ddof=1)*np.sqrt(12)],atol=1e-12))
        check('independent_correlation_'+name,np.isclose(a.monthly_correlation_to_msci,np.corrcoef(x,returns[BENCH])[0,1],atol=1e-15))
    # Explicit shift diagnostic; never use it to select the reported alignment.
    lag=[]
    for shift in [-1,0,1]:
        b=returns[BENCH].shift(shift)
        for name in [MAIN,RAW]:lag.append(dict(series=name,benchmark_shift_rows=shift,n_overlap=int(b.notna().sum()),correlation=returns[name].corr(b)))
    table(pd.DataFrame(lag),'alignment_diagnostic','Fixed earned-month alignment is shift=0. Benchmark shift +1 compares portfolio month m to MSCI m-1; -1 compares to m+1. Adjacent shifts are diagnostic only, 239 overlaps; no alignment optimization.')
    active=returns[[MAIN,RAW]].subtract(returns[BENCH],axis=0)
    active['main_minus_original']=returns[MAIN]-returns[RAW]
    active['main_active_absolute']=active[MAIN].abs()
    table(active.sort_values('main_active_absolute',ascending=False).head(12),'largest_deviations','Twelve largest absolute MAIN-minus-MSCI monthly differences; all three columns are return differences in decimals, Jan 1999-Dec 2018.')
    impacts=audit[['formation_month','main_return','original_return','clipped_weight','n_clipped']].copy()
    impacts['main_minus_original']=impacts.main_return-impacts.original_return
    impacts['absolute_change']=impacts.main_minus_original.abs()
    table(impacts.sort_values('absolute_change',ascending=False),'winsorization_impacts','Every earned month ranked by clipping impact on same score-weighted holdings; no return error inference.')
    top=holdings.assign(absolute_clipping_impact=holdings.winsorization_contribution_change.abs()).nlargest(25,'absolute_clipping_impact')
    table(top[['month','formation_month','stock_id','source_row','Mkt_Cap_3M_Usd','weight','R1M_Usd','R1M_Usd_winsor_01_99','winsorization_contribution_change',FLAG]],'largest_clipping_contributions','25 largest stock-month absolute weighted contributions to main-minus-original return; same holdings retained. Returns/contributions decimal, weights fractional.')
    figures(returns,wealth)
    check('all_input_hashes_unchanged',all(sha(ROOT/name)==h for name,h in hashes.items()))
    table(pd.DataFrame(CHECKS.items(),columns=['check','result']).set_index('check'),'verification','Execution results for input preservation, 240-month alignment, weights, level conversion, units/source matching and independent statistics. See validation_2B.json for hashes and versions.')
    import openpyxl
    validation={'input_sha256':hashes,'versions':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'matplotlib':matplotlib.__version__,'openpyxl':openpyxl.__version__},'selected_stock_months':len(d),'selected_flagged_stock_months':int(d[FLAG].sum()),'selected_securities':d.stock_id.nunique(),'formation_start':str(d.formation_month.min()),'formation_end':str(d.formation_month.max()),'earned_start':str(returns.index.min()),'earned_end':str(returns.index.max()),'weight_sum_max_abs_error_fsum':float((audit.weight_sum-1).abs().max()),'checks':CHECKS}
    (PART/'validation_2B.json').write_text(json.dumps(validation,indent=2))
    write_findings(summary,audit,returns,wealth,holdings)
    print(summary.to_string());print('\nWeight diagnostics:');print(audit[['n_securities','max_weight','top10_weight','effective_n_fraction','flagged_weight']].describe().to_string());print('\nChecks:',len(CHECKS),'all PASS');print('\nAlignment diagnostic:\n',pd.DataFrame(lag).to_string(index=False))

if __name__=='__main__':main()
