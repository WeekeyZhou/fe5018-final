"""Finalize 2A-(v): same rank diagnostics as question_2A.py, exact 2A-(iv) flag.
Run: python part2/python_source/question_2A5.py. Adds new outputs; no dataset is changed.
"""
from pathlib import Path
import hashlib
import json
import sys
import html
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from src import config, utils

PART = ROOT/'part2'
FLAG = 'pb_midpoint_low_bv_provisional_flag'
SAMPLES = ['All observations', 'Without provisional flags']
TESTS = ['P/B vs log(cap rank / book rank)', 'P/B vs cap rank within book-rank bins', 'P/B vs book rank within cap-rank bins']


def rho(a,b):
    if len(a)<3 or a.nunique()<2 or b.nunique()<2:
        return np.nan
    return float(spearmanr(a,b).statistic)


def main():
    path=PART/'data_cleaned_2A_with_provisional_pb_flag.csv.gz'
    input_hash=hashlib.sha256(path.read_bytes()).hexdigest()
    d=pd.read_csv(path,float_precision='round_trip')
    assert d[FLAG].dtype==bool
    assert d[FLAG].equals((d.Pb.eq(.5)&d.Bv.le(.03)).rename(FLAG))
    assert len(d)==283380 and d[FLAG].sum()==5720
    assert not d.duplicated(['stock_id','formation_month']).any()
    assert d[['Pb','Bv','Mkt_Cap_3M_Usd']].notna().all().all()
    assert d[['Bv','Mkt_Cap_3M_Usd']].gt(0).all().all(), 'Logs require positive scores; do not silently remove zero scores.'
    assert (pd.PeriodIndex(d.month,freq='M')==pd.PeriodIndex(d.formation_month,freq='M')+1).all()
    # Keep original vendor percentile scores in both samples. No reranking of inputs.
    monthly=[];conditional=[];pop=[]
    for sample,z in [(SAMPLES[0],d),(SAMPLES[1],d.loc[~d[FLAG]])]:
        pop.append(dict(sample=sample,n_stock_months=len(z),n_securities=z.stock_id.nunique(),n_months=z.month.nunique(),n_flagged=int(z[FLAG].sum())))
        for month,a in z.groupby('month',sort=True):
            month=pd.Period(month,freq='M')
            # Same proxy as question_2A.py: log(cap percentile)-log(book percentile).
            proxy=np.log(a.Mkt_Cap_3M_Usd)-np.log(a.Bv)
            monthly.append(dict(month=month,formation_month=month-1,sample=sample,n=len(a),rho=rho(a.Pb,proxy)))
            for control,variable,test,sign in [('Bv','Mkt_Cap_3M_Usd',TESTS[1],1),('Mkt_Cap_3M_Usd','Bv',TESTS[2],-1)]:
                bins=np.minimum((a[control]*5).astype(int),4)+1
                for b in range(1,6):
                    aa=a.loc[bins.eq(b)]
                    conditional.append(dict(month=month,formation_month=month-1,sample=sample,test=test,control_bin=b,n=len(aa),rho=rho(aa.Pb,aa[variable]),expected_sign=sign))
    monthly=pd.DataFrame(monthly);conditional=pd.DataFrame(conditional)
    records=[]
    for sample in SAMPLES:
        for test in TESTS:
            z=monthly[monthly['sample'].eq(sample)] if test==TESTS[0] else conditional[conditional['sample'].eq(sample)&conditional.test.eq(test)]
            v=z.rho.dropna();expected=-1 if test==TESTS[2] else 1
            records.append(dict(sample=sample,test=test,n_months=z.month.nunique(),n_correlation_cells=len(z),n_valid_cells=len(v),n_undefined_cells=z.rho.isna().sum(),median_rho=v.median(),mean_rho=v.mean(),min_rho=v.min(),max_rho=v.max(),expected_sign=expected,expected_sign_share=(v*expected).gt(0).mean()))
    summary=pd.DataFrame(records).set_index(['test','sample'])
    pop=pd.DataFrame(pop).set_index('sample')
    paired=monthly.pivot(index='month',columns='sample',values='rho')
    paired['rho_change_without_minus_all']=paired[SAMPLES[1]]-paired[SAMPLES[0]]
    paired['formation_month']=paired.index-1
    perbin=conditional.groupby(['test','control_bin','sample'],sort=False).agg(n_valid_cells=('rho','count'),median_rho=('rho','median'),mean_rho=('rho','mean'),min_n=('n','min'),max_n=('n','max'))
    for frame,name in [(monthly,'monthly'),(conditional,'conditional_cells'),(summary,'summary'),(pop,'samples'),(paired,'paired_monthly'),(perbin,'conditional_bins')]:
        utils.save_table(frame,'tab_2A5_'+name,float_format='%.10g')
    # Independently reproduce the all-row results from the original 2A run.
    old=pd.read_csv(config.TAB_DIR/'tab_2A_pb_sanity_monthly.csv')
    old=old.loc[old['sample'].eq('All rows')].set_index('month').spearman_pb_logrank_ratio
    new=monthly.loc[monthly['sample'].eq(SAMPLES[0])].set_index('month').rho
    assert np.allclose(new.to_numpy(),old.loc[new.index.astype(str)].to_numpy(),atol=1e-9)
    old_cond=pd.read_csv(config.TAB_DIR/'tab_2A_pb_conditional_monthly.csv')
    oc=old_cond[old_cond['sample'].eq('All rows')].copy()
    oc['test']=oc.control.map({'Bv':TESTS[1],'Mkt_Cap_3M_Usd':TESTS[2]})
    oc=oc.set_index(['month','test','control_bin']).spearman
    nc=conditional.loc[conditional['sample'].eq(SAMPLES[0])].copy()
    nc['month']=nc.month.astype(str);nc=nc.set_index(['month','test','control_bin']).rho
    assert np.allclose(nc,oc.loc[nc.index],atol=1e-9,equal_nan=True)
    # Alternative implementation: Spearman equals Pearson of average tied ranks.
    for sample,z in [(SAMPLES[0],d),(SAMPLES[1],d.loc[~d[FLAG]])]:
        for month,a in z.groupby('month'):
            p=np.log(a.Mkt_Cap_3M_Usd)-np.log(a.Bv)
            independent=a.Pb.rank(method='average').corr(p.rank(method='average'))
            expected=monthly.loc[monthly['sample'].eq(sample)&monthly.month.eq(pd.Period(month)), 'rho'].iloc[0]
            assert np.isclose(independent,expected,atol=1e-12)
    assert pop.loc[SAMPLES[1],'n_stock_months']==277660
    assert monthly.groupby('sample').size().eq(245).all()
    assert conditional.groupby('sample').size().eq(2450).all()
    assert monthly.n.sum()==len(d)+len(d)-5720
    assert hashlib.sha256(path.read_bytes()).hexdigest()==input_hash
    validation=dict(input_sha256=input_hash,checks={k:'PASS' for k in ['flag_exactly_matches_2A4_definition','all_rows_and_dates_valid','no_missing_or_nonpositive_proxy_inputs','all_row_proxy_matches_original_2A','all_row_conditional_checks_match_original_2A','independent_average_tied_rank_correlations_all_months_both_samples','exactly_5720_rows_omitted_only_in_diagnostic_subset','same_245_months_both_samples','all_4900_conditional_cells_accounted_for','input_dataset_unchanged']})
    (PART/'validation_2A5.json').write_text(json.dumps(validation,indent=2))

    config.apply_style()
    fig,axes=utils.new_fig('full',ncols=2)
    for label,color in zip(SAMPLES,config.COLORS[:2]):
        z=monthly[monthly['sample'].eq(label)]
        axes[0].plot(pd.PeriodIndex(z.formation_month,freq='M').to_timestamp(),z.rho,label='All' if label==SAMPLES[0] else 'Without flags',color=color)
    axes[0].set(title='Monthly rank-proxy correlation',xlabel='Formation year',ylabel='Spearman correlation',ylim=(.5,1))
    import matplotlib.dates as mdates
    axes[0].xaxis.set_major_locator(mdates.YearLocator(8));axes[0].xaxis.set_major_formatter(mdates.DateFormatter('%Y'));axes[0].legend(loc='lower right')
    y=np.arange(3)
    for j,(label,color) in enumerate(zip(SAMPLES,config.COLORS[:2])):
        vals=[summary.loc[(test,label),'median_rho'] for test in TESTS]
        axes[1].barh(y+(j-.5)*.30,vals,height=.28,color=color,label='All' if j==0 else 'Without flags')
    axes[1].set_yticks(y,['Ratio proxy','Cap | book bin','Book | cap bin']);axes[1].invert_yaxis()
    axes[1].set(title='Median rank associations',xlabel='Spearman correlation',xlim=(-1,1));axes[1].axvline(0,color=config.COLOR_MARKET,lw=.7)
    note=('Source: Class Part 2 CSV; formation Nov 1998-Mar 2019, all 1,207 supplied IDs.\n'
          'All: 283,380 rows; without Pb=0.50 & Bv<=0.03: 277,660. Conditional medians use month-bin cells.')
    utils.save_fig(fig,'fig_2A5_rank_sanity_flag_comparison',source=note)
    fig.savefig(config.FIG_DIR/'fig_2A5_rank_sanity_flag_comparison.svg');plt.close(fig)

    a=summary.loc[(TESTS[0],SAMPLES[0])];b=summary.loc[(TESTS[0],SAMPLES[1])]
    c=summary.loc[(TESTS[1],SAMPLES[0])];e=summary.loc[(TESTS[1],SAMPLES[1])]
    f=summary.loc[(TESTS[2],SAMPLES[0])];g=summary.loc[(TESTS[2],SAMPLES[1])]
    conclusion=(f'Because raw values are unavailable, we assess ordinal consistency rather than verify the accounting identity P/B = Market Cap / Book Equity. Across 245 months, the median Spearman correlation between P/B percentiles and log(cap percentile)-log(book-equity percentile) is {a.median_rho:.3f}; excluding the 5,720 provisional Pb=0.50 and Bv<=0.03 observations raises it to {b.median_rho:.3f}. Within book-rank bins, median P/B-cap correlations are {c.median_rho:.3f} and {e.median_rho:.3f}; within cap-rank bins, P/B-book correlations are {f.median_rho:.3f} and {g.median_rho:.3f}, respectively. Conditional medians summarize month-bin cells. These directional patterns are compatible with the valuation relationship. However, percentile transformations do not preserve ratios or reveal equity signs, and market cap is a three-month average. Stronger association after removing flagged rows does not establish data errors or nonpositive equity; retain the flags for sensitivity analysis.')
    (PART/'conclusion_2A5.md').write_text('# Question 2A-⑤: report conclusion\n\n'+conclusion+'\n')
    lines=['# Question 2A-⑤: rank-based sanity checks','',
      'Source: supplied class Part 2 CSV (mlfactor extract). Formation November 1998-March 2019 (245 months); earned-month labels December 1998-April 2019. This checks formation-date characteristics, not forward returns. All-sample universe: 1,207 supplied securities.', '',
      '## Results','',
      '| Diagnostic | Sample | Correlation cells | Median rho | Mean rho | Min rho | Max rho | Expected-sign share |',
      '|---|---|---:|---:|---:|---:|---:|---:|']
    for (test,sample),r in summary.iterrows():
        lines.append(f'| {test} | {sample} | {int(r.n_valid_cells):,} | {r.median_rho:.4f} | {r.mean_rho:.4f} | {r.min_rho:.4f} | {r.max_rho:.4f} | {r.expected_sign_share:.1%} |')
    lines += ['',f'All observations: 283,380 stock-months. Without flags: 277,660 stock-months (exactly 5,720 fewer). Both samples cover all 245 months; securities represented: {int(pop.loc[SAMPLES[0],"n_securities"]):,} and {int(pop.loc[SAMPLES[1],"n_securities"]):,}. No dataset rows are deleted. Two distinct conditional cells (highest cap-score bin, formation February and March 2019) contain only one security each in both samples. Their correlations are undefined: two of 1,225 cells per sample for the P/B-versus-book conditional check. They remain in the cell table as NaN; medians and expected-sign shares use the 1,223 defined cells. All monthly proxy and book-controlled cap correlations are defined. This sparse-bin issue is relevant to the previously flagged terminal sample contraction.', '',
      f'For the monthly proxy check, the median paired monthly change (without flags minus all) is {paired.rho_change_without_minus_all.median():.4f}; it is positive in {paired.rho_change_without_minus_all.gt(0).sum()} of 245 months. The change in the median correlation is {b.median_rho-a.median_rho:.4f}. These are different summaries and need not coincide.', '',
      '## Definitions and connection to the existing code','',
      '- Use the same diagnostics and bins as `part2/python_source/question_2A.py::pb_checks`: Spearman(Pb, log(Mkt_Cap_3M_Usd)-log(Bv)) within each formation month, plus Spearman(Pb, cap) inside book-score bins and Spearman(Pb, Bv) inside cap-score bins. All inputs are supplied percentile scores. Spearman uses average ranks for ties within each correlation sample.',
      '- The log expression is the log of a ratio of percentile scores. It is a heuristic, not log of raw market cap divided by raw equity. It has the same ordering as cap-score/book-score for positive scores. A correlation near one is not an accounting requirement, even if the raw identity is exact.',
      '- The five fixed control-score bins are [0,0.2), [0.2,0.4), [0.4,0.6), [0.6,0.8), [0.8,1]. Conditional checks use five cells per month per test: 1,225 cells per sample, equally weighted in summaries. The proxy uses 245 equally weighted monthly correlations per sample. Do not interpret conditional medians as medians of monthly-average correlations or pooled stock-month correlations.',
      '- The expected signs are positive for the ratio proxy and cap association, negative for the book association. Conditional tests hold the control only approximately constant within coarse bins; they do not isolate a structural derivative. Per-bin summaries and every monthly cell are supplied for audit.',
      '- The comparison omits only the observation-specific `pb_midpoint_low_bv_provisional_flag = (Pb == 0.50) & (Bv <= 0.03)`. It does not omit all Pb=0.50 rows, all low-Bv rows, or all histories of flagged securities. Supplied percentile values and fixed bins remain unchanged; Spearman ranks are naturally recomputed in the correlation sample.',
      '- Returns, winsorization, sample dates and the original cleaned files are unchanged. No portfolio weights or 2B/2C calculations are performed. This standalone script creates new 2A5 tables and figure files without rerunning earlier output writers.', '',
      '## What the checks establish and cannot establish','',
      'The broad positive ratio-proxy association, positive conditional cap association, and negative conditional book association are ordinal patterns compatible with the valuation relationship under ordinary positive-equity conditions. Their persistence in the two samples shows that the broad directional result is not solely driven by the flagged group. Report the paired comparison as a descriptive diagnostic.', '',
      'The original identity cannot be verified numerically: separate percentile transforms are nonlinear and distribution-dependent, so percentile(P/B) does not equal percentile(Market Cap)/percentile(Book Equity). Distances, currency units, magnitudes, equity signs, source definitions and timing cannot be recovered. The supplied numerator is a three-month average market cap, which may differ from the contemporaneous numerator used for P/B. Rounded ranks and ties further reduce information; unknown vendor imputation and preprocessing may affect the pattern.', '',
      'Improved association after the targeted exclusion cannot validate the exclusion itself: the rule deliberately selects a midpoint/low-book combination and mechanically changes composition and tied ranks. It is not proof of erroneous P/B, negative equity, missing-value imputation or a causal mechanism. Coarse controls leave residual variation and may mix economically different firms. Repeated observations and time dependence make naive independent-observation p-values inappropriate; none are claimed. Retain all data and the provisional flag pending metadata or raw-sign evidence.', '',
      '## Concise report conclusion','',conclusion,'',
      '## Reproduction and verification','',
      'Run `python part2/python_source/question_2A5.py` using the existing 2A dependencies. Requires the original 2A CSV outputs and the separate flagged dataset from `diagnostic_2A_pb_flag.py`. The original all-row proxy and conditional results are independently compared with the saved original 2A results (tolerance 1e-9 for CSV rounding). Every monthly proxy correlation in both samples is also verified as Pearson correlation of average tied ranks. Sample sizes, flag definition, dates, cell counts and input hashes are checked. See `validation_2A5.json`.', '',
      'New tables: `tab_2A5_summary.csv`, `tab_2A5_samples.csv`, `tab_2A5_monthly.csv`, `tab_2A5_paired_monthly.csv`, `tab_2A5_conditional_cells.csv`, `tab_2A5_conditional_bins.csv` under `output/tables/`. The paired PNG/SVG figure is `fig_2A5_rank_sanity_flag_comparison` under `output/figures/`. Earlier results and their catalog remain unchanged.']
    text='\n'.join(lines)+'\n'
    (PART/'findings_2A5.md').write_text(text)
    page='<!doctype html><html lang="en"><meta charset="utf-8"><title>2A-⑤ Rank sanity checks</title><style>body{font:14px Arial;max-width:1100px;margin:32px auto;line-height:1.5}img{width:6in;max-width:100%}table{border-collapse:collapse;font-size:12px}td,th{padding:7px;border-bottom:1px solid #ddd}pre{white-space:pre-wrap}</style><h1>2A-⑤ | Rank-based sanity checks</h1><p>'+html.escape(conclusion)+'</p><img src="../output/figures/fig_2A5_rank_sanity_flag_comparison.png" alt="Rank sanity checks with and without provisional flags">'+summary.to_html(float_format=lambda v:f'{v:.4f}')+'<pre>'+html.escape(text)+'</pre></html>'
    (PART/'review_2A5.html').write_text(page)
    print(summary.to_string());print('\n'+conclusion);print('\nPaired monthly change:',paired.rho_change_without_minus_all.describe().to_string())

if __name__=='__main__':main()
