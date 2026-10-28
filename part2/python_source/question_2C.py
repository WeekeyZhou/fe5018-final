"""Question 2C only. Run: python part2/python_source/question_2C.py.
Read-only reuse of validated 2B loader; adds outputs without rewriting 2A/2B.
"""
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
import question_2B as q2b

PART=ROOT/'part2'
FLAG=q2b.FLAG
STRATEGIES=['EW top 20%','Value score','Value score x cap']
MARKET='2B broad market'
UNIVERSES=['All observations (main)','Without provisional flags (sensitivity)']
RETURNS=['Winsorized (main)','Original (sensitivity)']
WEIGHT_NAMES={s:'weight_'+str(i+1) for i,s in enumerate(STRATEGIES)}
TABLES={};CHECKS={};FIGURES=[]


def check(name,condition):
    if not bool(condition):raise AssertionError(name)
    CHECKS[name]='PASS'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def table(df,name,description):
    name='tab_2C_'+name;TABLES[name]=(df.copy(),description)
    utils.save_table(df,name,float_format='%.12g')


def normalize(scores):
    x=np.asarray(scores,dtype=float)
    if not np.isfinite(x).all() or (x<0).any() or math.fsum(x)<=0:raise ValueError('Invalid unnormalized weight vector')
    w=x/math.fsum(x);before=w.copy();k=int(np.argmax(w))
    w[k]=1.-math.fsum(np.delete(w,k))
    if not (math.fsum(w)==1. and (w>=0).all() and np.max(np.abs(w-before))<2e-16):raise AssertionError('Normalization failed')
    return w


def value_scores(pb):
    # Validate the supplied grid first; do not silently round unknown scores.
    bucket=np.rint(np.asarray(pb)*100).astype(int)
    if not np.allclose(np.asarray(pb)*100,bucket,atol=1e-12,rtol=0) or not ((bucket>=1)&(bucket<=100)).all():
        raise ValueError('P/B no longer on supplied 0.01-1.00 grid; revisit endpoint rule.')
    return (101-bucket)/100.


def build(d,benchmark):
    holdings=[];audits=[];cuts=[];series=[];tie_returns=[]
    for month,z in d.groupby('month',sort=True):
        z=z.sort_values('stock_id').copy().reset_index(drop=True)
        v=value_scores(z.Pb);cap=z.Mkt_Cap_3M_Usd.to_numpy()
        z['value_score']=v
        for u,universe in enumerate(UNIVERSES):
            eligible=np.ones(len(z),dtype=bool) if u==0 else ~z[FLAG].to_numpy()
            n=int(eligible.sum());k=int(math.ceil(.2*n))
            # Primary key cheap P/B; secondary stock ID, never realized return.
            order=np.lexsort((z.stock_id.to_numpy(),z.Pb.to_numpy()))
            order=order[eligible[order]];selected=order[:k]
            top=np.zeros(len(z));top[selected]=1.
            cutoff=z.Pb.iloc[selected[-1]]
            below=eligible & z.Pb.lt(cutoff).to_numpy();equal=eligible & z.Pb.eq(cutoff).to_numpy()
            cuts.append(dict(month=month,formation_month=month-1,universe=universe,n_eligible=n,target_holdings=k,realized_share=k/n,cutoff_pb=cutoff,n_strictly_cheaper=int(below.sum()),n_at_cutoff=int(equal.sum()),n_selected_at_cutoff=k-int(below.sum()),n_tied_omitted=int(equal.sum())-(k-int(below.sum()))))
            unnormalized=[top,np.where(eligible,v,0.),np.where(eligible,v*cap,0.)]
            for strategy,scores in zip(STRATEGIES,unnormalized):
                w=normalize(scores)
                # Assign to the full original row set, including zero sensitivity weights.
                z[WEIGHT_NAMES[strategy]+('_all' if u==0 else '_without_flags')]=w
                main=math.fsum(w*z.R1M_Usd_winsor_01_99);raw=math.fsum(w*z.R1M_Usd)
                for version,ret in zip(RETURNS,[main,raw]):
                    series.append(dict(month=month,formation_month=month-1,universe=universe,return_version=version,strategy=strategy,portfolio_return=ret))
                audits.append(dict(month=month,formation_month=month-1,universe=universe,strategy=strategy,n_eligible=n,n_holdings=int((w>0).sum()),weight_sum=math.fsum(w),min_weight=w.min(),max_weight=w.max(),effective_n=1/np.sum(w*w),top10_weight=np.sort(w)[-10:].sum(),weighted_value_score=math.fsum(w*v),weighted_cap_score=math.fsum(w*cap),flagged_n_held=int(((w>0)&z[FLAG].to_numpy()).sum()),flagged_weight=math.fsum(w[z[FLAG].to_numpy()]),main_return=main,original_return=raw))
                if not np.isclose(main,np.average(z.R1M_Usd_winsor_01_99,weights=scores),atol=1e-15,rtol=0):raise AssertionError('Independent weighted return mismatch')
                if u==1 and (w[z[FLAG].to_numpy()]!=0).any():raise AssertionError('Excluded flags retain weight')
            # Ties-only diagnostic: EW all stocks at or cheaper than the cutoff.
            # This changes cardinality; never silently substituted for exact-k main.
            w_tie=normalize((below|equal).astype(float))
            tie_returns.append(dict(month=month,universe=universe,holdings_including_all_boundary_ties=int((w_tie>0).sum()),winsorized_return=math.fsum(w_tie*z.R1M_Usd_winsor_01_99),original_return=math.fsum(w_tie*z.R1M_Usd)))
            market_w=normalize(cap)
            # Market is always the validated full universe, including flags.
            if u==0:
                for version,col in zip(RETURNS,[q2b.MAIN,q2b.RAW]):
                    if not np.isclose(math.fsum(market_w*z['R1M_Usd_winsor_01_99' if version==RETURNS[0] else 'R1M_Usd']),benchmark.loc[month,col],atol=1e-12,rtol=0):raise AssertionError('2B benchmark reconciliation failed')
                audits.append(dict(month=month,formation_month=month-1,universe=universe,strategy=MARKET,n_eligible=len(z),n_holdings=len(z),weight_sum=math.fsum(market_w),min_weight=market_w.min(),max_weight=market_w.max(),effective_n=1/np.sum(market_w*market_w),top10_weight=np.sort(market_w)[-10:].sum(),weighted_value_score=math.fsum(market_w*v),weighted_cap_score=math.fsum(market_w*cap),flagged_n_held=int(z[FLAG].sum()),flagged_weight=math.fsum(market_w[z[FLAG].to_numpy()]),main_return=benchmark.loc[month,q2b.MAIN],original_return=benchmark.loc[month,q2b.RAW]))
            for version,col in zip(RETURNS,[q2b.MAIN,q2b.RAW]):
                series.append(dict(month=month,formation_month=month-1,universe=universe,return_version=version,strategy=MARKET,portfolio_return=benchmark.loc[month,col]))
        holdings.append(z)
    return pd.concat(holdings,ignore_index=True),pd.DataFrame(audits),pd.DataFrame(cuts),pd.DataFrame(series),pd.DataFrame(tie_returns)


def statistics(series):
    rows=[];wealth=[]
    for (universe,version,strategy),a in series.groupby(['universe','return_version','strategy'],sort=False):
        a=a.set_index('month').sort_index();r=a.portfolio_return
        w=utils.cumulative_value(r)
        rows.append(dict(universe=universe,return_version=version,strategy=strategy,n_months=len(r),annualized_arithmetic_return=utils.annualized_return(r,method='arithmetic'),annualized_geometric_return=utils.annualized_return(r,method='geometric'),annualized_volatility=utils.annualized_volatility(r),terminal_wealth=w.iloc[-1],cumulative_return=w.iloc[-1]-1))
        w=pd.concat([pd.Series([1.],index=pd.PeriodIndex(['1998-12'],freq='M',name='month')),w])
        wealth.append(pd.DataFrame(dict(month=w.index,universe=universe,return_version=version,strategy=strategy,wealth=w.to_numpy())))
        calc=[12*np.mean(r),np.expm1(np.log1p(r).sum()/20),np.std(r,ddof=1)*np.sqrt(12),np.exp(np.log1p(r).sum())]
        if not np.allclose(calc,[rows[-1][x] for x in ['annualized_arithmetic_return','annualized_geometric_return','annualized_volatility','terminal_wealth']],atol=1e-12,rtol=0):raise AssertionError('Independent stats mismatch')
    return pd.DataFrame(rows),pd.concat(wealth,ignore_index=True)


def figs(perf,wealth,final):
    config.apply_style()
    note=('Source: supplied Part 2 CSV; investment Jan 1999-Dec 2018, USD; all observed stocks.\n'
          'Main: 1/99 winsorized returns, 1.01-Pb Value score; monthly rebalance. Benchmark: validated 2B market.')
    def save(fig,name):
        name='fig_2C_'+name;utils.save_fig(fig,name,source=note)
        fig.savefig(config.FIG_DIR/(name+'.svg'));FIGURES.append(name);plt.close(fig)
    fig,ax=utils.new_fig('full')
    z=wealth[wealth.universe.eq(UNIVERSES[0])&wealth.return_version.eq(RETURNS[0])]
    for strategy,color in zip(STRATEGIES+[MARKET],config.COLORS[:3]+[config.COLOR_MARKET]):
        a=z[z.strategy.eq(strategy)];ax.plot(pd.PeriodIndex(a.month,freq='M').to_timestamp(how='end').normalize(),a.wealth,label=strategy,color=color)
    ax.set(title='2C | Value portfolios: growth of $1 (main analysis)',xlabel='Investment month end',ylabel='Investment value (USD)')
    ax.xaxis.set_major_locator(mdates.YearLocator(4));ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'));ax.legend(loc='upper left',ncol=2)
    save(fig,'cumulative_wealth')
    fig,axes=utils.new_fig('full',ncols=2)
    z=perf[perf.universe.eq(UNIVERSES[0])&perf.return_version.eq(RETURNS[0])].set_index('strategy').loc[STRATEGIES+[MARKET]]
    labels=['EW top 20%','Value','Value x cap','Market']
    for ax,col,title in zip(axes,['annualized_arithmetic_return','annualized_volatility'],['Annualized arithmetic return','Annualized volatility']):
        ax.barh(labels,z[col],color=config.COLORS[:3]+[config.COLOR_MARKET]);ax.invert_yaxis();ax.set(title=title,xlabel='Annual rate');utils.percent_axis(ax,'x')
    save(fig,'return_and_risk')
    fig,ax=utils.new_fig('full')
    names=['All, winsorized (main)','All, original','No flags, winsorized','No flags, original']
    cases=[(UNIVERSES[0],RETURNS[0]),(UNIVERSES[0],RETURNS[1]),(UNIVERSES[1],RETURNS[0]),(UNIVERSES[1],RETURNS[1])]
    y=np.arange(3)
    for j,((u,r),name) in enumerate(zip(cases,names)):
        v=perf[perf.universe.eq(u)&perf.return_version.eq(r)].set_index('strategy').loc[STRATEGIES,'annualized_arithmetic_return']
        ax.barh(y+(j-1.5)*.18,v,height=.17,label=name,color=config.COLORS[j])
    ax.set_yticks(y,STRATEGIES);ax.invert_yaxis();ax.set(title='2C | Return robustness: clipping and provisional flags',xlabel='Annualized arithmetic return')
    utils.percent_axis(ax,'x');ax.legend(loc='lower right',fontsize=6.5)
    save(fig,'robustness')


def documents(perf,audit,cuts,tie_summary,validation):
    p=perf[perf.universe.eq(UNIVERSES[0])&perf.return_version.eq(RETURNS[0])].set_index('strategy').loc[STRATEGIES+[MARKET]]
    final=audit[audit.formation_month.eq(pd.Period('2018-11'))&audit.universe.eq(UNIVERSES[0])].set_index('strategy').loc[STRATEGIES+[MARKET]]
    top=p.annualized_arithmetic_return.idxmax();risk=p.annualized_volatility.idxmax()
    minhold=final.loc[STRATEGIES].n_holdings.idxmin();maxweight=final.loc[STRATEGIES].max_weight.idxmax()
    def listvals(col):return ', '.join(f'{p.loc[s,col]:.2%}' for s in STRATEGIES)
    max_weight_text=', '.join(format(final.loc[s,'max_weight'],'.2%') for s in STRATEGIES)
    original=perf[perf.universe.eq(UNIVERSES[0])&perf.return_version.eq(RETURNS[1])].set_index('strategy')
    excluded=perf[perf.universe.eq(UNIVERSES[1])&perf.return_version.eq(RETURNS[0])].set_index('strategy')
    sensitivity_text=(f'Original-return arithmetic averages are {", ".join(format(original.loc[s,"annualized_arithmetic_return"],".2%") for s in STRATEGIES)}; excluding flags with winsorized returns gives {", ".join(format(excluded.loc[s,"annualized_arithmetic_return"],".2%") for s in STRATEGIES)}. The ordering persists, but return levels are sensitive to extremes, especially for top-20% selection.')
    draft=(f'We reverse the supplied P/B percentile grid using Value score = 1.01 - Pb; lower P/B therefore receives higher Value weight without treating percentiles as raw ratios. Ties share scores; the equal-weight portfolio selects ceil(20% of N) stocks, with cutoff ties resolved by stock ID. All provisional P/B flags remain in the main sample.\n\n'
           f'Over January 1999-December 2018, annualized arithmetic returns for equal-weight top-20%, Value-score, and Value-score-times-cap portfolios are {listvals("annualized_arithmetic_return")}, respectively, versus {p.loc[MARKET,"annualized_arithmetic_return"]:.2%} for the 2B market. Their annualized volatilities are {listvals("annualized_volatility")}, versus {p.loc[MARKET,"annualized_volatility"]:.2%}. {top} has the highest arithmetic return; {risk} has the highest volatility. Arithmetic return is the main average-return comparison; geometric returns and wealth separately describe compounded investor outcomes.\n\n'
           f'At November 2018 formation, the three Value portfolios hold {", ".join(format(int(final.loc[s,"n_holdings"]),",") for s in STRATEGIES)} stocks, with maximum weights {max_weight_text}. Top-20% selection concentrates holdings; multiplying Value by cap scores shifts the size-rank mix. {sensitivity_text} Causal small-cap premia, erroneous P/B coding and nonpositive book equity remain unconfirmed.')
    (PART/'findings_2C.md').write_text('# Question 2C: concise English findings\n\n'+draft+'\n')
    methods='''# Question 2C: construction, interpretation and limitations

## Main universe, dates and benchmark

Use all observations selected by the read-only `question_2B.load_stock()` loader, which validates original 2A values, winsorization, flags and source rows without writing any 2B outputs. Formation December 1998-November 2018 is selected through `config.PERIODS['2B']`/`utils.select_period`, also the assignment window for 2C. Earned-month index is January 1999-December 2018, exactly formation + one calendar month; do not shift rows a second time. No missing return or score is imputed or silently removed. All 279,575 in-window stock-months, including 5,630 provisional flags, remain eligible in the main construction (5,720 flags exist in the full 2A history). Eligibility does not use future persistence or realized returns. The 2B benchmark is read from its saved monthly-return table and independently reconciled to score-weighted source returns, with only CSV-rounding tolerance. No MSCI/HML joins or 2D tracking-error, spread-correlation or factor regressions are computed.

## Reversing P/B scores into Value scores

The supplied Pb values lie on the verified grid {0.01,0.02,...,1.00}. Define v = 1.01 - Pb, reversing the 100 ordered buckets. Pb=0.01 maps to v=1.00; Pb=1.00 maps to v=0.01; Pb=0.50 maps to v=0.51. Tied Pb observations receive identical v. Implementation verifies the grid before integer bucket encoding (101-bucket)/100 to avoid floating-point subtraction artifacts; an unexpected grid raises an error. This is a fixed affine reversal of the supplied percentile categories, not reconstruction of raw Book-to-Price or a new percentile estimation. It preserves original tie masses and the provider's reference distribution. It is defensible as an increasing exposure score for cheapness under ordinary positive-equity conditions. Book-equity signs are unavailable, so that interpretation is provisional for suspicious observations.

Using 1/Pb would treat percentile distances as raw valuation magnitudes and overweight the lowest bucket arbitrarily; it is not used. Endpoint handling matters: 1-Pb would assign zero weight at Pb=1.00, whereas the chosen grid reversal preserves a positive lowest score. A within-month midrank percentile reversal is another possible convention and would redistribute ties and exposure spacing. It is not silently substituted here. The affine reversal is a documented implementation choice; performance does not validate it economically. Scores remain unchanged after the sensitivity exclusion so that changes are not additionally driven by restandardization.

## Portfolio formulas and ties

1. Equal-weight top 20%: for eligible count N, choose k=ceil(0.20*N). Sort by Pb ascending (v descending), then anonymized stock_id ascending. Exactly k stocks receive weight 1/k, subject only to a machine residual correction. This rounds the target count up by less than one stock. A cutoff tie can be split; the stock-ID tie-break is deterministic and independent of returns, but economically arbitrary and not rank-neutral. It does not establish that chosen tied names are cheaper. A monthly cutoff table logs the tie size, selected/omitted tied names and realized selection fraction. A separately labelled all-boundary-ties diagnostic equally weights every stock at or below the same cutoff; that changes cardinality and is never substituted for the main exact-k portfolio.
2. Value-score weighted: w_i = v_i / sum(v). All eligible stocks have strictly positive weights. Equal Pb scores receive equal weights. The highest raw Book-to-Price ratio cannot be recovered.
3. Value-score x cap: w_i = v_i*s_i / sum(v*s), s=Mkt_Cap_3M_Usd. Equal Pb scores can receive different weights because cap scores differ. This intentionally tempers the pure Value score with size rank, not actual capitalization or book-equity amounts.

All portfolios rebalance monthly with no leverage, shorts or cash. The normalizer corrects the largest weight by a floating residual below 2e-16; accurately summed weights equal 1.0 exactly. A portfolio return is sum of formation weights times the next month's decimal return. Main returns use the established monthly 1st/99th-percentile clipped values. No weights depend on returns. Weight-zero names in the top-20% portfolio are unselected holdings, not deleted dataset observations. Every original in-window row is retained in the new holdings file with main and sensitivity weights.

## Performance comparison and sensitivities

Use arithmetic annual return (12*mean(monthly return)) as the primary comparison of average strategy returns, appropriate for comparing the average one-period performance of monthly-rebalanced long-only strategies. Also show geometric annual return (20-year CAGR), which is appropriate for compounded investment growth. These are different questions; do not label arithmetic annual return as compound performance. Annualized volatility is sample std(ddof=1)*sqrt(12), never average stock volatility or the volatility of annual averages. Shared utilities implement all measures and cumulative wealth from $1 on 31 December 1998. Wealth tables include the initial seed (241 observations per strategy/case); return series contain 240. None of these measures is a risk-adjusted or causal Value premium.

The 2x2 robustness design crosses (all observations vs excluding the exact provisional flag) with (winsorized vs original returns). Raw and clipped returns use identical weights within each eligibility universe. In the flag-exclusion variant, only the 5,630 flagged in-window stock-months become ineligible; their observations remain in the holdings file with zero sensitivity weights. No entire security history is discarded. Recompute N, k and normalizations among eligible rows without reranking the fixed Value scores. The saved 2B benchmark remains the full-universe market in both universes; its original-return series is used in original-return sensitivity tables. Thus exclusion changes the Value opportunity set relative to a fixed full-universe benchmark; it is not a matched-universe market comparison.

## Findings versus hypotheses

Weighted means of the provided cap and Value scores, effective holdings 1/sum(w^2), max weights and top-10 weights are observable diagnostics. Lower weighted cap scores indicate a lower market-cap RANK mix, not measured raw cap exposure, a Fama-French size loading or an attribution of excess return. Actual valuation ratios, capitalization distances, liquidity, trading costs and equity signs are unavailable. Score multiplication does not produce actual capitalization weighting. The count/concentration differences follow portfolio construction; the performance ranking is an empirical sample result and need not generalize.

The flag-exclusion rule selects a suspicious midpoint/low-book combination; it has not identified confirmed errors or nonpositive equity. Changes in performance cannot prove either interpretation. Ties, historical universe selection, the 1999 membership anomaly, interior missing stock-month rows, unknown point-in-time accounting information, survivorship, corporate events, and ex-post return clipping remain limitations from 2A/2B. No absent or terminal return is filled with zero or -100%. Transaction costs, taxes, market impact and float/investability adjustments are omitted. Arithmetic outperformance alone does not prove that Value or small-cap risk is rewarded after controls. No 2D analysis is performed.

## Reproduction and preservation

Run `python part2/python_source/question_2C.py` in the completed repository, using existing `requirements_2B.txt`. The script imports shared config/utils and the read-only 2B stock loader, reads the validated 2A/2B inputs, and writes only new 2C files. `holdings_2C.csv.gz` contains the original keys, Pb, Value score, cap score, both returns, flag, and six weight columns (three full-universe and three no-flag). The main and robustness CSV tables are catalogued under `output/tables/tab_2C_catalog.csv`; figures are paired PNG/SVG. The catalog and review page supply table sources and universes. CSV returns, weights and proportions are decimals. Existing raw data, shared files, other members' work and prior results are unchanged. No commits or pushes.
'''
    # Quantified interpretation and all four robustness cases, without causal claims.
    means=audit[audit.universe.eq(UNIVERSES[0])].groupby('strategy')[['weighted_cap_score','weighted_value_score','effective_n']].median().loc[STRATEGIES+[MARKET]]
    methods+='\n## Measured rank exposures and final concentration\n\nMedian monthly portfolio-weighted market-cap scores are '+', '.join(f'{s}: {means.loc[s,"weighted_cap_score"]:.3f}' for s in STRATEGIES+[MARKET])+'. These are observed score differences, not actual capitalization ratios.\n\n'
    methods+='Median monthly weighted Value scores are '+', '.join(f'{s}: {means.loc[s,"weighted_value_score"]:.3f}' for s in STRATEGIES+[MARKET])+'. In this sample, higher arithmetic returns and volatility coincide with stronger cheapness scores and lower cap ranks. Multiplying by cap scores shifts the observed mix toward higher cap ranks and weakens cheapness scores relative to pure Value weighting. These measurements describe the portfolios; without raw exposures, controls and bias-free source data, they do not attribute returns causally to Value or small-cap premia.\n\n'
    methods+=f'Among Value portfolios, {minhold} has the fewest final holdings and {maxweight} has the largest final single-stock weight. Full-support score portfolios need not have smaller maximum weights than an equal-weight selected portfolio; the product of two scores and its normalization determine the result.\n\n'
    for s in STRATEGIES:
        vals=perf[perf.strategy.eq(s)].set_index(['universe','return_version'])
        base=vals.loc[(UNIVERSES[0],RETURNS[0])]
        raw=vals.loc[(UNIVERSES[0],RETURNS[1])];ex=vals.loc[(UNIVERSES[1],RETURNS[0])]
        methods+=f'{s}: original minus winsorized arithmetic annual return = {(raw.annualized_arithmetic_return-base.annualized_arithmetic_return)*100:.3f} percentage points; excluding flags minus main winsorized arithmetic annual return = {(ex.annualized_arithmetic_return-base.annualized_arithmetic_return)*100:.3f} percentage points.\n\n'
    methods+='The original-return/no-flags combination is also reported in the full 2x2 table. Top-20% flags may have zero main weight, but exclusion can still change the selected count because eligible N changes.\n\nAll-boundary-ties versus exact-k EW diagnostics:\n\n'+tie_summary.to_string(index=False)+'\n'
    (PART/'methodology_2C.md').write_text(methods)
    catalog=pd.DataFrame([dict(file=n+'.csv',description=desc) for n,(_,desc) in TABLES.items()])
    utils.save_table(catalog,'tab_2C_catalog')
    view=p[['annualized_arithmetic_return','annualized_geometric_return','annualized_volatility','terminal_wealth']].copy()
    for c in view.columns[:-1]:view[c]=view[c].map(lambda x:f'{x:.2%}')
    view.terminal_wealth=view.terminal_wealth.map(lambda x:f'${x:.3f}')
    content=['<!doctype html><html lang="en"><meta charset="utf-8"><title>FE5108 2C review</title><style>body{font:14px Arial;max-width:1100px;margin:32px auto;line-height:1.5}img{width:6in;max-width:100%}table{border-collapse:collapse;font-size:12px}td,th{padding:8px;border-bottom:1px solid #ddd}th{background:#edf3f6}pre{white-space:pre-wrap}</style><h1>2C: Value portfolio construction</h1>']
    for para in draft.split('\n\n'):content.append('<p>'+html.escape(para)+'</p>')
    content+=['<h2>Main performance</h2>'+view.to_html(),'<p>Source: supplied Part 2 CSV, all observed stocks; investment Jan 1999-Dec 2018. Main returns winsorized 1/99. Market is validated 2B score-weighted benchmark.</p>','<h2>Final formation: November 2018</h2>'+final[['n_holdings','max_weight','effective_n','top10_weight']].to_html(float_format=lambda x:f'{x:.6f}')]
    for fig in FIGURES:content.append(f'<p><img src="../output/figures/{fig}.png" alt="{fig}"></p>')
    content+=['<h2>All robustness statistics (decimal returns)</h2>'+perf.to_html(index=False,float_format=lambda x:f'{x:.6f}'),'<h2>Methods and limitations</h2><pre>'+html.escape(methods)+'</pre>','<h2>Verification</h2><pre>'+html.escape(json.dumps(validation,indent=2))+'</pre>',catalog.to_html(index=False),'</html>']
    (PART/'review_2C.html').write_text('\n'.join(content))


def main():
    paths=[PART/'data_cleaned_2A.csv.gz',PART/'data_cleaned_2A_with_provisional_pb_flag.csv.gz',config.TAB_DIR/'tab_2B_monthly_returns.csv',config.TAB_DIR/'tab_2B_performance.csv',Path(__file__).resolve().parent/'question_2B.py',ROOT/'src/config.py',ROOT/'src/utils.py',config.FILE_PART2]
    hashes={str(p.relative_to(ROOT)):sha(p) for p in paths}
    d=q2b.load_stock()
    for name,result in q2b.CHECKS.items():CHECKS['2B_loader_'+name]=result
    benchmark=pd.read_csv(config.TAB_DIR/'tab_2B_monthly_returns.csv',index_col='month',float_precision='round_trip');benchmark.index=pd.PeriodIndex(benchmark.index,freq='M',name='month')
    expected=pd.period_range('1999-01','2018-12',freq='M',name='month')
    check('benchmark_exact_240_months',benchmark.index.equals(expected))
    check('all_value_inputs_finite',np.isfinite(d[['Pb','Mkt_Cap_3M_Usd','R1M_Usd','R1M_Usd_winsor_01_99']]).all().all())
    check('mapping_endpoints_and_ties',np.array_equal(value_scores([.01,.50,.50,1]),[1.,.51,.51,.01]))
    # Synthetic tie case: exact-k selection must ignore returns and retain ID order.
    test=pd.DataFrame({'stock_id':[9,4,1,7,3,8],'Pb':[.01,.01,.01,.2,.5,1.]})
    order=np.lexsort((test.stock_id,test.Pb));check('synthetic_cutoff_tie_rule',test.stock_id.iloc[order[:math.ceil(.2*len(test))]].tolist()==[1,4])
    h,audit,cuts,series,ties=build(d,benchmark)
    check('all_original_selected_rows_preserved',h.source_row.nunique()==len(d)==len(h) and np.array_equal(np.sort(h.source_row),np.sort(d.source_row)))
    check('all_main_observations_including_5630_flags_eligible',audit[audit.universe.eq(UNIVERSES[0])&audit.strategy.eq(STRATEGIES[1])].n_holdings.sum()==len(d) and h[FLAG].sum()==5630)
    check('all_six_weights_nonnegative',h[[c for c in h if c.startswith('weight_')]].ge(0).all().all())
    check('all_weight_sums_exactly_one',audit.weight_sum.eq(1.).all())
    check('exact_k_cardinality',audit[audit.strategy.eq(STRATEGIES[0])].n_holdings.to_numpy().tolist()==cuts.target_holdings.to_list())
    check('top20_never_selects_less_cheap_over_strictly_cheaper',cuts.n_strictly_cheaper.le(cuts.target_holdings).all() and cuts.n_selected_at_cutoff.gt(0).all())
    check('no_flagged_weight_in_sensitivity',audit[audit.universe.eq(UNIVERSES[1])].flagged_weight.eq(0).all())
    check('all_16_series_have_240_complete_returns',series.groupby(['universe','return_version','strategy']).size().eq(240).all() and np.isfinite(series.portfolio_return).all() and series.portfolio_return.gt(-1).all())
    check('independent_weighted_returns_all_cases',True)
    check('2B_market_reproduced_from_source_weights',True)
    perf,wealth=statistics(series)
    check('independent_arithmetic_CAGR_volatility_compounding',True)
    check('all_16_wealth_series_have_seed_plus_240_months',wealth.groupby(['universe','return_version','strategy']).size().eq(241).all() and wealth[wealth.month.eq(pd.Period('1998-12'))].wealth.eq(1.).all())
    # Saved 2B performance is reproduced, allowing only prior CSV rounding.
    bp=pd.read_csv(config.TAB_DIR/'tab_2B_performance.csv',index_col='series')
    for version,oldname in zip(RETURNS,[q2b.MAIN,q2b.RAW]):
        a=perf[perf.strategy.eq(MARKET)&perf.universe.eq(UNIVERSES[0])&perf.return_version.eq(version)].iloc[0]
        check('validated_2B_performance_matches_'+version,np.allclose(a[['annualized_arithmetic_return','annualized_geometric_return','annualized_volatility','terminal_wealth']].to_numpy(dtype=float),bp.loc[oldname,['annualized_arithmetic_return','annualized_geometric_return','annualized_volatility','terminal_value_of_1']].to_numpy(dtype=float),atol=1e-10,rtol=0))
    holdcols=['month','formation_month','stock_id','source_row','Pb','value_score','Mkt_Cap_3M_Usd','R1M_Usd','R1M_Usd_winsor_01_99',FLAG]+[c for c in h if c.startswith('weight_')]
    h[holdcols].to_csv(PART/'holdings_2C.csv.gz',index=False,float_format='%.17g',compression={'method':'gzip','mtime':0})
    saved=pd.read_csv(PART/'holdings_2C.csv.gz',float_precision='round_trip')
    for u in range(2):
        for strategy in STRATEGIES:
            col=WEIGHT_NAMES[strategy]+('_all' if u==0 else '_without_flags')
            if not saved.groupby('month')[col].apply(math.fsum).eq(1.).all():raise AssertionError('Serialized weights mismatch')
    check('serialized_all_six_weight_sets_sum_exactly_one',True)
    check('serialized_source_keys_and_flags_preserved',saved.source_row.equals(h.source_row) and saved[FLAG].equals(h[FLAG]))
    final=audit[audit.formation_month.eq(pd.Period('2018-11'))]
    source='Supplied Part 2 CSV; formation Dec 1998-Nov 2018 / investment Jan 1999-Dec 2018. Main retains all observations and uses 1/99 clipped decimal returns; flags excluded only in labelled sensitivity. Fixed validated 2B market.'
    table(perf,'performance_all_cases',source+' Annualized arithmetic=12*mean (main comparison), geometric=CAGR, volatility=sample std*sqrt(12); wealth starts at $1.')
    mainperf=perf[perf.universe.eq(UNIVERSES[0])&perf.return_version.eq(RETURNS[0])].set_index('strategy').loc[STRATEGIES+[MARKET]]
    table(mainperf,'performance_main',source+' Main four-portfolio comparison, decimal units.')
    mainret=series[series.universe.eq(UNIVERSES[0])&series.return_version.eq(RETURNS[0])].pivot(index='month',columns='strategy',values='portfolio_return').reindex(columns=STRATEGIES+[MARKET])
    table(mainret,'monthly_returns_main',source+' Exactly 240 monthly return rows.')
    table(series,'monthly_returns_all_cases',source+' Long-form 16 series, 240 months each; benchmark repeated unchanged across eligibility cases.')
    table(wealth,'cumulative_wealth_all_cases',source+' Includes initial $1 seed at Dec 1998 (241 rows per series).')
    table(final.set_index(['universe','strategy']),'final_weights_summary','Formation Nov 2018 / earned Dec 2018; supplied Part 2 securities. Holdings count positive weights; max/top10 weights are fractions, effective N=1/sum(w^2). Benchmark fixed 2B.')
    table(audit,'monthly_weight_audit',source+' Full concentration, score exposure and flags audit; each weight sum=1.')
    table(cuts,'top20_cutoff_ties',source+' ceil(0.2*N), ascending Pb then stock ID; every split cutoff tie recorded.')
    exposure=audit.groupby(['universe','strategy'],sort=False)[['n_holdings','max_weight','top10_weight','effective_n','weighted_value_score','weighted_cap_score','flagged_weight']].agg(['mean','median','min','max'])
    table(exposure,'exposure_concentration',source+' Descriptive monthly weighted score and concentration summaries; scores do not measure raw cap or valuation distances.')
    # Full final source-level audit, including zero weights.
    table(h[h.formation_month.eq(pd.Period('2018-11'))][holdcols],'final_holdings','All Nov 2018 formation rows, original scores/returns/flags and six weight columns. Zero weights retained. Source: supplied Part 2 CSV.')
    tie_stats=[]
    for universe in UNIVERSES:
        for version,col in zip(RETURNS,['winsorized_return','original_return']):
            t=ties[ties.universe.eq(universe)].set_index('month')[col]
            exact=series[series.universe.eq(universe)&series.return_version.eq(version)&series.strategy.eq(STRATEGIES[0])].set_index('month').portfolio_return
            tie_stats.append(dict(universe=universe,return_version=version,all_ties_arithmetic_return=utils.annualized_return(t,method='arithmetic'),exact_k_arithmetic_return=utils.annualized_return(exact,method='arithmetic'),annualized_arithmetic_difference=12*(t-exact).mean(),maximum_absolute_monthly_difference=(t-exact).abs().max()))
    tie_summary=pd.DataFrame(tie_stats)
    table(ties,'top20_all_boundary_ties_returns',source+' Extra diagnostic includes entire boundary-tie bucket with equal weights, changing holding count; not main portfolio.')
    table(tie_summary,'top20_boundary_tie_sensitivity',source+' All-boundary-ties versus exact-k EW only; return differences in decimals, not basis points.')
    # Convenient same-strategy deltas without computing any 2D excess-return series.
    deltas=[]
    for strategy in STRATEGIES:
        vals=perf[perf.strategy.eq(strategy)].set_index(['universe','return_version'])
        base=vals.loc[(UNIVERSES[0],RETURNS[0])]
        for (u,r),row in vals.iterrows():
            deltas.append(dict(strategy=strategy,universe=u,return_version=r,arithmetic_return_change_vs_main=row.annualized_arithmetic_return-base.annualized_arithmetic_return,CAGR_change_vs_main=row.annualized_geometric_return-base.annualized_geometric_return,volatility_change_vs_main=row.annualized_volatility-base.annualized_volatility,terminal_wealth_change_vs_main=row.terminal_wealth-base.terminal_wealth))
    table(pd.DataFrame(deltas),'robustness_changes',source+' Same-strategy scalar changes relative to all-observation/winsorized main; not 2D factor-spread analytics.')
    impacts=[]
    for strategy in STRATEGIES:
        z=h[['month','formation_month','stock_id','source_row','Pb','Mkt_Cap_3M_Usd','R1M_Usd','R1M_Usd_winsor_01_99',FLAG]].copy()
        z['strategy']=strategy
        z['main_weight']=h[WEIGHT_NAMES[strategy]+'_all']
        z['original_minus_winsorized_contribution']=z.main_weight*(z.R1M_Usd-z.R1M_Usd_winsor_01_99)
        z['absolute_contribution']=z.original_minus_winsorized_contribution.abs()
        impacts.append(z.nlargest(15,'absolute_contribution'))
    table(pd.concat(impacts,ignore_index=True),'largest_clipping_contributions',source+' Fifteen largest absolute stock-month original-minus-winsorized weighted contributions per Value strategy, full-universe weights. Not evidence of confirmed errors.')
    monthly_impact=audit[audit.universe.eq(UNIVERSES[0])].copy()
    monthly_impact['original_minus_winsorized_return']=monthly_impact.original_return-monthly_impact.main_return
    table(monthly_impact[['month','formation_month','strategy','original_return','main_return','original_minus_winsorized_return']],'monthly_clipping_impacts',source+' Same full-universe weights; differences isolate return clipping, not membership or score changes.')
    figs(perf,wealth,final)
    check('all_input_hashes_unchanged',all(sha(ROOT/n)==v for n,v in hashes.items()))
    table(pd.DataFrame(CHECKS.items(),columns=['check','result']).set_index('check'),'verification','Checks for monthly alignment, original data/2B matching, grid/ties, six weight sets, eligibility, serialization and independent performance calculations. Source: executed 2C code.')
    validation={'input_sha256':hashes,'versions':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'matplotlib':matplotlib.__version__},'selected_stock_months':len(d),'selected_flagged_stock_months':int(d[FLAG].sum()),'full_history_flagged_stock_months':5720,'months_per_series':240,'main_value_score':'(101 - integer_pb_bucket)/100 = 1.01 - Pb','top20_rule':'ceil(0.20*N), ties by ascending stock_id','checks':CHECKS}
    (PART/'validation_2C.json').write_text(json.dumps(validation,indent=2))
    documents(perf,audit,cuts,tie_summary,validation)
    print(mainperf.to_string());print('\nFinal main weights:\n',final[final.universe.eq(UNIVERSES[0])][['strategy','n_holdings','max_weight','effective_n','weighted_cap_score']].to_string(index=False));print('\nAll cases:\n',perf.to_string(index=False));print('\nChecks:',len(CHECKS),'PASS')

if __name__=='__main__':main()
