"""Question 2D. Run: python part2/python_source/question_2D.py. Reads saved 2B/2C only.
Adds 2D results; never rewrites prior files or downloads replacement factor data.
"""
from pathlib import Path
import hashlib,html,json,platform,re,sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from src import config,utils
PART=ROOT/'part2'
STRATEGIES=['EW top 20%','Value score','Value score x cap']
LABELS=['S1: EW top 20%','S2: Value score','S3: Value x cap','FF HML']
VERSIONS=['Winsorized (main)','Original (sensitivity)']
CHECKS={};TABLES={}
FACTOR_URL='https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_factors.html'
SIX_URL='https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/six_portfolios.html'


def check(name,condition):
    if not bool(condition):raise AssertionError(name)
    CHECKS[name]='PASS'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def table(d,name,description):
    name='tab_2D_'+name;TABLES[name]=(d.copy(),description)
    utils.save_table(d,name,float_format='%.12g')


def load_hml(expected):
    s=pd.read_excel(config.FILE_FF_MSCI,sheet_name=config.SHEET_FF3,header=None)
    # Locate the single monthly header. Annual header is deliberately not read.
    headers=[i for i,row in s.iterrows() if str(row.iloc[1]).strip()=='Mkt-RF' and str(row.iloc[3]).strip()=='HML']
    monthly_headers=[i for i in headers if i+1<len(s) and re.fullmatch(r'\d{6}(?:\.0)?',str(s.iat[i+1,0]).strip())]
    check('one_monthly_factor_header',len(monthly_headers)==1)
    start=monthly_headers[0]+1;end=start
    while end<len(s) and re.fullmatch(r'\d{6}(?:\.0)?',str(s.iat[end,0]).strip()):end+=1
    block=s.iloc[start:end,[0,3]].copy();block.columns=['YYYYMM','HML_percent']
    check('annual_block_not_included',block.YYYYMM.astype(str).str.fullmatch(r'\d{6}(?:\.0)?').all() and end<len(s) and pd.isna(s.iat[end,0]))
    block['HML_percent']=pd.to_numeric(block.HML_percent,errors='raise')
    block=utils.to_monthly_index(block.set_index('YYYYMM'))
    check('factor_months_unique_and_contiguous',block.index.is_unique and block.index.equals(pd.period_range(block.index.min(),block.index.max(),freq='M',name='month')))
    check('provided_factor_vintage_ends_July2023',str(block.index.max())=='2023-07')
    check('no_factor_missing_or_sentinels',np.isfinite(block.HML_percent).all() and not block.HML_percent.isin([-99.99,-999]).any())
    block['HML_decimal']=utils.pct_to_decimal(block.HML_percent)
    selected=block.reindex(expected)
    check('HML_exact_240_complete_months',len(selected)==240 and selected.index.equals(expected) and selected.notna().all().all())
    check('HML_percent_decimal_conversion',np.allclose(selected.HML_decimal.to_numpy()*100,selected.HML_percent.to_numpy(),atol=1e-14,rtol=0))
    check('Jan1999_HML_reference_minus4_60_percent',np.isclose(selected.loc['1999-01','HML_percent'],-4.60) and np.isclose(selected.loc['1999-01','HML_decimal'],-.046))
    table(selected,'hml_conversion','Source: professor FF/MSCI workbook, FF - 3 factor returns monthly block (2023-07 vintage). Jan 1999-Dec 2018. Original percent and decimal conversion; no forward-month shift.')
    refs=block.reindex(pd.PeriodIndex(['1995-01','1999-01','2008-10','2018-12'],freq='M',name='month'))
    table(refs,'hml_reference_values','HML loader cross-member reference values from supplied workbook; Jan 1995 is outside evaluation window. No data fetched from current French library.')
    return selected.HML_decimal.rename('FF HML')


def main():
    paths=[config.FILE_FF_MSCI,config.TAB_DIR/'tab_2B_monthly_returns.csv',config.TAB_DIR/'tab_2C_monthly_returns_main.csv',config.TAB_DIR/'tab_2C_monthly_returns_all_cases.csv',ROOT/'src/config.py',ROOT/'src/utils.py']
    hashes={str(p.relative_to(ROOT)):sha(p) for p in paths}
    expected=pd.period_range('1999-01','2018-12',freq='M',name='month')
    b=pd.read_csv(paths[1],index_col='month',float_precision='round_trip');b.index=pd.PeriodIndex(b.index,freq='M',name='month')
    c=pd.read_csv(paths[2],index_col='month',float_precision='round_trip');c.index=pd.PeriodIndex(c.index,freq='M',name='month')
    cases=pd.read_csv(paths[3],float_precision='round_trip');cases['month']=pd.PeriodIndex(cases.month,freq='M');cases['formation_month']=pd.PeriodIndex(cases.formation_month,freq='M')
    check('saved_2B_and_2C_exact_240_months',b.index.equals(expected) and c.index.equals(expected))
    check('saved_formation_equals_investment_minus_one',cases.month.eq(cases.formation_month+1).all())
    check('2B_benchmark_in_2C_matches',np.allclose(c['2B broad market'],b['Market: winsorized (main)'],atol=1e-12,rtol=0))
    check('all_saved_return_values_finite',np.isfinite(b.to_numpy()).all() and np.isfinite(c.to_numpy()).all() and np.isfinite(cases.portfolio_return).all())
    hml=load_hml(expected)
    stats=[];matrices={};aligned={};source_tables=[]
    # Primary eligibility is all observations; flag exclusions were studied in 2C.
    for version,bcol in zip(VERSIONS,['Market: winsorized (main)','Market: original (sensitivity)']):
        z=cases[cases.universe.eq('All observations (main)')&cases.return_version.eq(version)]
        check('unique_strategy_month_keys_'+version,not z.duplicated(['month','strategy']).any())
        z=z.pivot(index='month',columns='strategy',values='portfolio_return').reindex(index=expected,columns=STRATEGIES+['2B broad market'])
        check('complete_240_returns_all_four_portfolios_'+version,z.shape==(240,4) and np.isfinite(z.to_numpy()).all())
        check('fixed_saved_2B_market_'+version,np.allclose(z['2B broad market'],b[bcol],atol=1e-12,rtol=0))
        if version==VERSIONS[0]:check('main_strategy_series_reproduce_saved_2C',np.allclose(z[STRATEGIES],c[STRATEGIES],atol=1e-12,rtol=0))
        active=z[STRATEGIES].subtract(b[bcol],axis=0)
        active.columns=LABELS[:3];active=active.join(hml)
        check('aligned_four_series_240_complete_'+version,active.shape==(240,4) and active.index.equals(expected) and np.isfinite(active.to_numpy()).all())
        corr=active.corr(method='pearson')
        check('symmetric_unit_diagonal_bounded_correlation_'+version,np.allclose(corr,corr.T,atol=1e-15) and np.allclose(np.diag(corr),1,atol=1e-15) and (corr.abs()<=1+1e-14).all().all())
        check('independent_numpy_correlation_'+version,np.allclose(corr,np.corrcoef(active.to_numpy(),rowvar=False),atol=1e-14,rtol=0))
        check('positive_semidefinite_correlation_'+version,np.linalg.eigvalsh(corr).min()>-1e-12)
        for strategy,label in zip(STRATEGIES,LABELS[:3]):
            a=active[label]
            te=utils.tracking_error(z[strategy],b[bcol])
            # Independent formula uses explicitly centered sum of squares and N-1.
            centered=a.to_numpy()-a.to_numpy().mean()
            independent=np.sqrt(np.dot(centered,centered)/(len(a)-1))*np.sqrt(12)
            check('independent_TE_'+version+'_'+strategy,np.isclose(te,independent,atol=1e-14,rtol=0))
            check('active_subtraction_'+version+'_'+strategy,np.allclose(a.to_numpy(),z[strategy].to_numpy()-b[bcol].to_numpy(),atol=1e-15,rtol=0))
            stats.append(dict(return_version=version,strategy=strategy,n_months=len(a),monthly_active_std=a.std(ddof=1),annualized_tracking_error=te,HML_correlation=corr.loc[label,'FF HML']))
        suffix='main' if version==VERSIONS[0] else 'original'
        source=z.rename(columns={'2B broad market':'2B market'}).copy();source['formation_month']=(source.index-1).astype(str)
        table(source,'portfolio_returns_'+suffix,'Source: validated 2C Value returns and 2B full-universe market, investment Jan 1999-Dec 2018. Decimal returns. '+version+'. All provisional flags retained.')
        table(active,'active_and_hml_'+suffix,'Jan 1999-Dec 2018, exactly 240 jointly aligned monthly decimal observations. Three Value-minus-2B-market active returns plus supplied HML. '+version+'. Sources: saved 2B/2C and professor FF workbook.')
        table(corr,'correlation_'+suffix,'Pearson 4x4 correlation of three active returns and FF HML; 240 common Jan 1999-Dec 2018 months; '+version+'. All provisional flags retained. HML is unchanged across return versions.')
        matrices[version]=corr;aligned[version]=active
    check('HML_identical_across_sensitivity_versions',aligned[VERSIONS[0]]['FF HML'].equals(aligned[VERSIONS[1]]['FF HML']))
    results=pd.DataFrame(stats).set_index(['return_version','strategy'])
    table(results,'tracking_error_and_hml','Jan 1999-Dec 2018, all-stock Value portfolios vs validated 2B full market. TE=sample std of monthly active returns*sqrt(12); TE decimals. HML correlations use identical 240 dates. Main winsorized; original sensitivity changes both strategy and market returns.')
    delta=results.loc[VERSIONS[1]][['annualized_tracking_error','HML_correlation']]-results.loc[VERSIONS[0]][['annualized_tracking_error','HML_correlation']]
    table(delta,'original_minus_main','Same weights/eligibility; original minus winsorized TE (decimal annual volatility) and HML correlation. Benchmark original returns in original case.')
    table(matrices[VERSIONS[1]]-matrices[VERSIONS[0]],'correlation_change_original_minus_main','Entrywise original-minus-winsorized Pearson correlation changes; identical dates, weights, eligibility and HML. Jan 1999-Dec 2018.')
    config.apply_style()
    for version,suffix in zip(VERSIONS,['main','original']):
        corr=matrices[version]
        fig,ax=utils.new_fig('full')
        im=ax.imshow(corr,vmin=-1,vmax=1,cmap='RdBu_r',aspect='auto')
        short=['S1 active','S2 active','S3 active','FF HML']
        ax.set_xticks(range(4),short);ax.set_yticks(range(4),short)
        ax.set_xlabel('Monthly return series');ax.set_ylabel('Monthly return series');ax.grid(False)
        ax.set_title('2D | Active returns and HML'+(': main correlations' if suffix=='main' else ': original-return sensitivity'))
        for i in range(4):
            for j in range(4):ax.text(j,i,f'{corr.iloc[i,j]:.3f}',ha='center',va='center',fontsize=8,color='white' if abs(corr.iloc[i,j])>.65 else 'black')
        colorbar=fig.colorbar(im,ax=ax,pad=.03);colorbar.set_label('Pearson correlation')
        note=('Source: saved 2B/2C and supplied FF HML; Jan 1999-Dec 2018, 240 months; all stocks retained.\n'
              'S1: EW top 20%; S2: Value score; S3: Value x cap. Active = strategy - 2B market; '+('1/99 winsorized.' if suffix=='main' else 'original returns.'))
        name='fig_2D_correlation_'+suffix;utils.save_fig(fig,name,source=note);fig.savefig(config.FIG_DIR/(name+'.svg'));plt.close(fig)
    fig,ax=utils.new_fig('full')
    y=np.arange(3)
    for j,version in enumerate(VERSIONS):
        ax.barh(y+(j-.5)*.30,results.loc[version].annualized_tracking_error.reindex(STRATEGIES),height=.28,label=version,color=config.COLORS[j])
    ax.set_yticks(y,STRATEGIES);ax.invert_yaxis();ax.set(title='2D | Annualized tracking error to the 2B market',xlabel='Sample monthly active-return standard deviation x sqrt(12)');utils.percent_axis(ax,'x');ax.legend(loc='lower right')
    utils.save_fig(fig,'fig_2D_tracking_error',source='Source: validated 2B/2C, all observed stocks; Jan 1999-Dec 2018, 240 monthly USD returns.\nMain: 1/99 winsorized; sensitivity: original strategy and market returns; identical holdings and dates.')
    fig.savefig(config.FIG_DIR/'fig_2D_tracking_error.svg');plt.close(fig)
    check('input_files_unchanged',all(sha(ROOT/n)==v for n,v in hashes.items()))
    table(pd.DataFrame(CHECKS.items(),columns=['check','result']).set_index('check'),'verification','Executed 2D checks: 240-date alignment, factor percent conversion, source-return identity, active subtraction, independent TE/correlation, symmetry/diagonal/bounds/PSD and input preservation.')
    validation={'input_sha256':hashes,'versions':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'matplotlib':matplotlib.__version__},'months':240,'start':'1999-01','end':'2018-12','factor_source':'Professor workbook, monthly FF3 block, 2023-07 vintage','methodology_sources':[FACTOR_URL,SIX_URL],'checks':CHECKS}
    (PART/'validation_2D.json').write_text(json.dumps(validation,indent=2))
    mainstats=results.loc[VERSIONS[0]];corr=matrices[VERSIONS[0]];raw=results.loc[VERSIONS[1]]
    best=mainstats.annualized_tracking_error.idxmin();closest=mainstats.HML_correlation.idxmax()
    te=', '.join(f'{mainstats.loc[s,"annualized_tracking_error"]:.2%}' for s in STRATEGIES)
    rh=', '.join(f'{mainstats.loc[s,"HML_correlation"]:.3f}' for s in STRATEGIES)
    draft=(f'For January 1999-December 2018, annualized tracking errors of EW top-20%, Value-score, and Value-score-times-cap active returns relative to the 2B market are {te}, respectively. Value-score-times-cap has the lowest tracking error, consistent with retaining broad holdings and incorporating the same cap scores used by the market benchmark. Their pairwise active-return correlations range from {corr.iloc[:3,:3].to_numpy()[np.triu_indices(3,1)].min():.3f} to {corr.iloc[:3,:3].to_numpy()[np.triu_indices(3,1)].max():.3f}, indicating substantial shared variation.\n\n'
           f'Correlations with HML are {rh}; Value-score-times-cap is closest. This is consistent with HML using value-weighted size/book-to-market portfolios, although HML is a long-short high-minus-low factor with equal small/big-leg averaging, whereas our portfolios are monthly-rebalanced long-only rank-weighted strategies measured relative to a constructed market. Correlations support a common Value-related component, not identical factor exposures or causality. Original-return sensitivity preserves the lowest-tracking-error and highest-HML-correlation rankings; data-selection, percentile-score and clipping limitations remain.')
    (PART/'findings_2D.md').write_text('# Question 2D: concise English findings\n\n'+draft+'\n\nHML construction source: [Kenneth French factor definitions]('+FACTOR_URL+').\n')
    methods='''# Question 2D: definitions, methodology and interpretation

## Returns, dates and benchmark

Read validated 2C monthly returns and subtract the saved 2B broad market in the SAME earned month. Active_i,m = Value_i,m - Market_m. Both portfolio components use 2A monthly 1st/99th-percentile clipped stock returns in the main case; main Value construction, rank reversal, top-20% cutoff/ties and provisional flag retention are unchanged from 2C. No weights are reconstructed or selected using HML. Formation December 1998-November 2018 corresponds to investment January 1999-December 2018, exactly 240 months. The input 2C formation labels are verified as earned month minus one; HML is already dated by earned month and is not shifted.

Active returns are return differences, not relative gross returns (1+Value)/(1+market)-1. They are not standalone long-only investment returns. No additional risk-free subtraction is needed for this differential. No compounding or geometric mean is used to calculate tracking error or correlations.

## HML loading and units

Only the professor-provided FF/MSCI workbook is used numerically. Locate the FF - 3 factor returns MONTHLY header followed by a six-digit YYYYMM key; consume only the consecutive monthly block, stopping at the blank separator before Annual Factors. Reject missing data/sentinels, duplicate or noncontiguous dates, and nonnumeric HML. Use utils.to_monthly_index for YYYYMM and utils.pct_to_decimal for percent/100. The source vintage ends July 2023; do not replace it with today's revised factor download. January 1999 HML is -4.60 percent, i.e. -0.046 decimal. Save the full 240-row conversion audit and reference values including January 1995 for cross-member checking. Source-return matching to the validated decimal 2B/2C series establishes the other three series' unit convention; observed magnitude alone is not the unit test. No series are multiplied by 100 internally. Every correlation uses the same complete 240-row panel, so no pairwise missing-data sample differences occur.

## Tracking error and correlation

Use utils.tracking_error(Value,Market), which computes sample standard deviation of monthly differences (ddof=1) times sqrt(12). Independently calculate sqrt(sum((a-mean(a))^2)/(240-1))*sqrt(12) from NumPy arrays. Tracking error is volatility of deviation, not average under/outperformance and not the volatility of the Value portfolio itself. A smaller value means closer return tracking, not necessarily better investment performance.

Pearson correlation is computed on the three active series plus HML. Independently verify with numpy.corrcoef, symmetry, diagonal ones, bounds [-1,1], and positive semidefiniteness within numerical tolerance. Correlations are scale-free, but correct decimal units remain essential to active subtraction and tracking error. Main and original-return 4x4 matrices, their differences, underlying series and TE/HML summaries are all saved. Original-return sensitivity uses the same full-universe weights and dates but BOTH Value and 2B market original-return series; HML is unchanged. This isolates return cleaning rather than eligibility or benchmark specification. The flag-exclusion sensitivity is retained in 2C and not silently made the main 2D universe.

## Interpretation and limitations

Value-score-times-cap incorporates the market's cap score in its weights and holds the broad eligible universe, differing by a Value tilt. This provides a plausible construction-based explanation for lower tracking error than the concentrated cheap-stock selection or pure Value-score weighting. Common support alone is insufficient: pure Value also holds all names, while its weighting differs more from the market. Measured tracking error, not the formula alone, establishes the sample ranking.

Pairwise positive correlations support shared active-return movements; they are not proof of identical underlying securities or equal factor loadings. All active series subtract the same market, creating common benchmark terms in covariance, so not all co-movement need be a distinct Value signal. Positive HML correlations are additional evidence compatible with Value-related exposure. Correlation does not establish causation, risk-adjusted alpha, a pure Value premium, orthogonality to market/size or robustness across regimes. No factor regressions, attribution or hypothesis-test p-values are claimed.

HML is defined from six value-weighted portfolios formed by intersecting two size groups with three book-to-market groups. Its formula is one half of (Small Value + Big Value) minus one half of (Small Growth + Big Growth). Thus it uses value weighting WITHIN the component portfolios but equal averaging across the small/big Value and Growth legs; it is not one capitalization-weighted long-short portfolio over all firms. Component portfolios are formed at June-end, using NYSE median size and 30th/70th book-to-market breakpoints, with the documented lagged book/market definitions and positive book equity. Our market-relative, long-only monthly percentile-weight strategies differ in formation, selection, score magnitudes, size balance, rebalance schedule and treatment of unobservable book-equity signs. The cap-modulated Value strategy's stronger HML association is plausible given component value weighting; it is not mechanically required and does not demonstrate HML replication. Low-P/B and book-to-price order reversal is economically interpretable for positive equity, but raw ratios/signs remain unavailable here.

The anonymized security selection, 1999 membership issues, missing security-month rows, survivorship and point-in-time data uncertainties from 2A remain. Percentile cap scores cannot recover capitalization distances. Ex-post stock-return winsorization changes active series; sensitivity quantifies this without identifying which original observations are errors. Repeated histories and market regimes limit interpretation of sample correlations; none proves complete US coverage or security-level data accuracy. No claim is made about today's revised factor data matching the historical workbook.

## Sources and reproduction

Methodology only (accessed 28 October 2026):
- Kenneth French factor definitions: FACTOR_URL
- Six size/book-to-market portfolios: SIX_URL

All numerical HML values come from the supplied workbook; web pages are used solely to interpret the methodology. Run python part2/python_source/question_2D.py using existing part2/python_source/requirements_2B.txt. Required saved 2B/2C tables are not rerun or changed. Source hashes, package versions and all check results are in validation_2D.json. The package contains only new 2D files and is an overlay for the completed repository. No shared files, original datasets or prior outputs are modified; no commits or pushes.
'''.replace('FACTOR_URL',FACTOR_URL).replace('SIX_URL',SIX_URL)
    methods+='\n## Numerical robustness\n\n'
    for s in STRATEGIES:methods+=f'{s}: main TE {mainstats.loc[s,"annualized_tracking_error"]:.4%}, original TE {raw.loc[s,"annualized_tracking_error"]:.4%}; HML correlation {mainstats.loc[s,"HML_correlation"]:.4f} versus {raw.loc[s,"HML_correlation"]:.4f}.\n\n'
    (PART/'methodology_2D.md').write_text(methods)
    catalog=pd.DataFrame([dict(file=n+'.csv',description=d) for n,(_,d) in TABLES.items()]);utils.save_table(catalog,'tab_2D_catalog')
    view=mainstats[['annualized_tracking_error','HML_correlation']].copy();view.annualized_tracking_error=view.annualized_tracking_error.map(lambda x:f'{x:.2%}');view.HML_correlation=view.HML_correlation.map(lambda x:f'{x:.4f}')
    page=['<!doctype html><html lang="en"><meta charset="utf-8"><title>FE5108 2D review</title><style>body{font:14px Arial;max-width:1050px;margin:32px auto;line-height:1.5}table{border-collapse:collapse;font-size:13px}th,td{padding:8px;border-bottom:1px solid #ddd}th{background:#edf3f6}img{width:6in;max-width:100%}pre{white-space:pre-wrap}</style><h1>2D: Tracking error and Value correlations</h1>']
    for para in draft.split('\n\n'):page.append('<p>'+html.escape(para)+'</p>')
    page+=[view.to_html(),'<h2>Main correlation matrix</h2>'+corr.to_html(float_format=lambda x:f'{x:.4f}'),'<p>Source: saved 2B/2C and supplied FF HML; investment Jan 1999-Dec 2018, 240 common months; all provisional flags retained.</p>']
    for name in ['correlation_main','tracking_error','correlation_original']:page.append(f'<p><img src="../output/figures/fig_2D_{name}.png" alt="{name}"></p>')
    page+=['<h2>All return versions (TE in decimals)</h2>'+results.to_html(float_format=lambda x:f'{x:.6f}'),'<h2>Methods and limitations</h2><pre>'+html.escape(methods)+'</pre>','<h2>Verification</h2><pre>'+html.escape(json.dumps(validation,indent=2))+'</pre>',catalog.to_html(index=False),'</html>']
    (PART/'review_2D.html').write_text('\n'.join(page))
    print(results.to_string());print('\nMain matrix:\n'+corr.to_string());print('\nChecks:',len(CHECKS),'PASS')

if __name__=='__main__':main()
