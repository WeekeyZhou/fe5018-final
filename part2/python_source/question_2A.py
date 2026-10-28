"""Question 2A only. Run from any directory: python /path/to/repo/part2/python_source/question_2A.py.

No raw/shared files are changed; no observations are deleted or imputed.
Internal returns are decimal; month index denotes the earned return month.
"""
from __future__ import annotations
import hashlib
import html
import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import scipy
from scipy.stats import spearmanr
from src import config, utils

PART = ROOT / 'part2'
FEATURES = ['Pb', 'Bv', 'Vol3Y_Usd', 'Mkt_Cap_3M_Usd']
ALPHA = .01  # main interpretation: clip lower 1% AND upper 1%, retaining central 98%
TABLES = {}
FIGURES = []


def table(df, name, description):
    """CSV numbers retain precision; exhibit descriptions live in the catalog/report."""
    name = 'tab_2A_' + name
    TABLES[name] = (df.copy(), description)
    utils.save_table(df, name, float_format='%.10g')


def source(note=''):
    return ('Source: Class Part 2 CSV (mlfactor extract); all supplied securities.\n'
            'Formation: Nov 1998-Mar 2019; forward returns: Dec 1998-Apr 2019. ' + note)


def save(fig, name, note=''):
    name = 'fig_2A_' + name
    utils.save_fig(fig, name, source=source(note))
    # Shared saver uses bbox=tight. Also supply PDF-free, vector SVG for report editing.
    fig.savefig(config.FIG_DIR / (name + '.svg'))
    FIGURES.append(name)
    plt.close(fig)


def time_axis(ax):
    ax.xaxis.set_major_locator(mdates.YearLocator(4))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax.set_xlabel('Formation month (return earned in following month)')


def load():
    d = pd.read_csv(config.FILE_PART2)
    required = ['stock_id', 'date', *FEATURES[:2], 'R1M_Usd', *FEATURES[2:]]
    if list(d.columns) != required:
        raise ValueError(f'Unexpected schema: {list(d.columns)}')
    if d[['stock_id', 'date']].isna().any().any():
        raise ValueError('Missing stock/date keys; investigate before continuing.')
    dt = pd.to_datetime(d.date, format='%m/%d/%Y', errors='raise')
    if not dt.dt.is_month_end.all():
        raise ValueError('Non-month-end dates; investigate.')
    # Use team helper, then shift the calendar label rather than shifting rows.
    d = utils.to_monthly_index(d.set_index('date'), fmt='%m/%d/%Y')
    d['formation_month'] = d.index
    d.index = d.index + 1
    d.index.name = 'month'  # earned month
    d['source_row'] = np.arange(1, len(d) + 1)  # one-based CSV data row, excluding header
    if d.reset_index().duplicated(['stock_id', 'formation_month']).any():
        raise ValueError('Duplicate stock-month keys; no automatic deletion.')
    for col in [*FEATURES, 'R1M_Usd']:
        if not pd.api.types.is_numeric_dtype(d[col]):
            raise ValueError(f'Non-numeric {col}; no silent coercion.')
        if np.isinf(d[col]).any():
            raise ValueError(f'Infinite {col}; investigate before clipping.')
    if ((d[FEATURES] < 0) | (d[FEATURES] > 1)).any().any():
        raise ValueError('Percentile outside [0,1]; investigate.')
    return d.sort_values(['month', 'stock_id'])


def membership(d):
    months = pd.period_range(d.formation_month.min(), d.formation_month.max(), freq='M')
    ids = pd.Index(sorted(d.stock_id.unique()), name='stock_id')
    full = pd.MultiIndex.from_product([months, ids], names=['formation_month', 'stock_id'])
    observed = pd.MultiIndex.from_frame(d[['formation_month', 'stock_id']])
    present = pd.Series(full.isin(observed), index=full).unstack('stock_id')
    # Forward returns are matched to the observed formation stock, not next month's membership.
    valid = d.assign(valid=d.R1M_Usd.notna().astype(int)).pivot(index='formation_month', columns='stock_id', values='valid').reindex(index=months, columns=ids).fillna(0).astype(bool)
    prev = present.shift(1, fill_value=False)
    nxt = present.shift(-1, fill_value=False)
    later = present.iloc[::-1].cumsum().iloc[::-1].gt(0).shift(-1, fill_value=False)
    earlier = present.cumsum().gt(0).shift(1, fill_value=False)
    interior = ~present & earlier & later
    m = pd.DataFrame(index=months + 1)
    m.index.name = 'month'
    def add(name, vals):
        m[name] = np.asarray(vals)
    add('formation_month', months.astype(str))
    add('stocks_present', present.sum(axis=1))
    add('valid_returns', valid.sum(axis=1))
    m['missing_return_rows'] = m.stocks_present - m.valid_returns
    m['coverage_present'] = m.valid_returns / m.stocks_present.replace(0, np.nan)
    add('all_sample_ids', len(ids))
    m['presence_all_sample_ids'] = m.stocks_present / len(ids)
    add('interior_absent_rows', interior.sum(axis=1))
    m['coverage_within_observed_spells'] = m.valid_returns / (m.stocks_present + m.interior_absent_rows)
    add('arrivals_vs_prior_month', (present & ~prev).sum(axis=1))
    add('first_seen', (present & ~earlier).sum(axis=1))
    add('reappearances', (present & ~prev & earlier).sum(axis=1))
    add('departures_vs_prior_month', (~present & prev).sum(axis=1))
    add('departures_later_reappear', (~present & prev & later).sum(axis=1))
    add('departures_not_seen_again', (~present & prev & ~later).sum(axis=1))
    add('next_month_absent', (present & ~nxt).sum(axis=1))
    add('next_month_absent_later_reappear', (present & ~nxt & later).sum(axis=1))
    add('next_month_absent_not_seen_again', (present & ~nxt & ~later).sum(axis=1))
    # First / last boundary has no observed comparator. Never label all final rows as exits.
    for col in ['arrivals_vs_prior_month', 'departures_vs_prior_month', 'departures_later_reappear', 'departures_not_seen_again', 'reappearances']:
        m.loc[m.index[0], col] = np.nan
    for col in ['next_month_absent', 'next_month_absent_later_reappear', 'next_month_absent_not_seen_again']:
        m.loc[m.index[-1], col] = np.nan
    m['stock_count_change'] = m.stocks_present.diff()
    m['stock_count_change_fraction'] = m.stocks_present.pct_change(fill_method=None)
    # Transparent descriptive trigger, not a hypothesis test or a deletion rule.
    m['count_change_flag_2pct'] = m.stock_count_change_fraction.abs().ge(.02)
    m['gross_transition_fraction'] = (m.arrivals_vs_prior_month + m.departures_vs_prior_month) / m.stocks_present.shift(1)
    m['gross_transition_flag_10pct'] = m.gross_transition_fraction.ge(.10)
    spells = d.groupby('stock_id').formation_month.agg(first_seen='min', last_seen='max', observed_months='size')
    spells['span_months'] = spells.last_seen.astype('int64') - spells.first_seen.astype('int64') + 1
    spells['interior_absent_months'] = spells.span_months - spells.observed_months
    spells['right_censored_at_sample_end'] = spells.last_seen.eq(months[-1])
    # Detailed absent rows are diagnostic only: never fabricated returns in the cleaned file.
    gaps = interior.stack()
    gaps = gaps[gaps].rename('interior_absent').reset_index()
    gaps['month'] = gaps.formation_month + 1
    table(m, 'monthly_validation', 'Monthly counts, observed-row coverage, membership transitions and full-sample presence. Fractions are 0-1; index is earned month.')
    table(spells, 'stock_spells', 'Security-level observed spans; an interior gap is not a missing value on an existing row.')
    table(gaps, 'interior_gaps', 'All missing stock-month rows between each security\'s first and last observed formation month; diagnostic only.')
    table(m.loc[m.count_change_flag_2pct | m.gross_transition_flag_10pct], 'unusual_months', 'Absolute monthly stock-count change >=2% or gross arrivals plus departures >=10% of prior count; boundaries separately discussed. No exclusions.')
    return m, present, interior, spells


def winsorize(d):
    d = d.copy()
    q = d.groupby(level='month').R1M_Usd.quantile([ALPHA, 1-ALPHA], interpolation='linear').unstack()
    q.columns = ['return_lower_01', 'return_upper_99']
    for c in q:
        d[c] = d.index.map(q[c])
    d['R1M_Usd_winsor_01_99'] = d.R1M_Usd.clip(lower=d.return_lower_01, upper=d.return_upper_99)
    d['return_clipped_lower'] = d.R1M_Usd.lt(d.return_lower_01)
    d['return_clipped_upper'] = d.R1M_Usd.gt(d.return_upper_99)
    d['return_missing'] = d.R1M_Usd.isna()
    d['pb_midpoint_flag'] = d.Pb.eq(.5)
    d['bv_low_decile_flag'] = d.Bv.le(.10)
    g = d.groupby(level='month')
    q['formation_month'] = (q.index - 1).astype(str)
    q['n_nonmissing'] = g.R1M_Usd.count()
    q['n_clipped_lower'] = g.return_clipped_lower.sum()
    q['n_clipped_upper'] = g.return_clipped_upper.sum()
    q['raw_mean'] = g.R1M_Usd.mean()
    q['winsorized_mean'] = g.R1M_Usd_winsor_01_99.mean()
    table(q, 'winsor_cutoffs', 'Monthly linear-interpolated 1st/99th percentile cutoffs and strict-tail clipping counts. Returns in decimals; no pooled cutoffs.')
    summaries = []
    for label, x in [('Raw', d.R1M_Usd), ('Monthly 1/99 winsorized', d.R1M_Usd_winsor_01_99)]:
        a = x.describe(percentiles=[.001,.005,.01,.05,.5,.95,.99,.995,.999]).to_dict()
        a.update(series=label, skewness=x.skew(), excess_kurtosis=x.kurt(), below_minus_100pct=x.lt(-1).sum(), above_100pct=x.gt(1).sum())
        summaries.append(a)
    table(pd.DataFrame(summaries).set_index('series'), 'return_summary', 'Pooled stock-month return statistics, not portfolio performance; decimal returns, sample standard deviation.')
    tails = d.loc[d.return_clipped_lower | d.return_clipped_upper].copy()
    tails['extremeness_absolute_return'] = tails.R1M_Usd.abs()
    table(tails.sort_values('extremeness_absolute_return', ascending=False), 'clipped_observations', 'Every changed stock-month with original return and its monthly cutoffs; no rows removed.')
    extremes = pd.concat([d.nsmallest(10,'R1M_Usd'), d.nlargest(10,'R1M_Usd')]).sort_values('R1M_Usd')
    table(extremes, 'extreme_returns', 'Ten smallest and ten largest raw returns with security IDs, formation and earned months, and clipped values.')
    # Alternative interpretation is diagnostic, never substituted silently into the main cleaned column.
    rows=[]
    for a in [.005,.01]:
        qq = g.R1M_Usd.quantile([a,1-a], interpolation='linear').unstack()
        z=d.R1M_Usd.clip(lower=d.index.map(qq[a]), upper=d.index.map(qq[1-a]))
        rows.append(dict(lower_quantile=a, upper_quantile=1-a, n_changed=int((z.ne(d.R1M_Usd)&d.R1M_Usd.notna()).sum()), mean=z.mean(), std=z.std(), min=z.min(), max=z.max()))
    table(pd.DataFrame(rows), 'winsor_interpretation_sensitivity', 'Central 99% (0.5/99.5) versus main 1/99 clipping (central 98%). Both monthly. No strategy backtests.')
    return d, q


def pb_checks(d):
    frequencies = pd.DataFrame({c:d[c].value_counts().sort_index() for c in FEATURES})
    frequencies.index.name='percentile_value'
    table(frequencies, 'percentile_frequencies', 'Exact observed percentile masses. P/B is percentile-transformed, not a z-score or an actual valuation ratio.')
    rows=[]
    for label,mask in [('Pb = 0.50', d.Pb.eq(.5)), ('Pb != 0.50',d.Pb.ne(.5))]:
        a=d.loc[mask]
        rows.append(dict(group=label,n=len(a),share=len(a)/len(d),bv_mean=a.Bv.mean(),bv_median=a.Bv.median(),bv_le_010_share=a.Bv.le(.1).mean(),bv_eq_001_share=a.Bv.eq(.01).mean(),cap_median=a.Mkt_Cap_3M_Usd.median(),return_mean=a.R1M_Usd.mean()))
    table(pd.DataFrame(rows).set_index('group'), 'pb_midpoint_groups', 'P/B midpoint concentration and association with low book-value ranks. These ranks do not identify the sign of book equity.')
    monthly=[]
    conditional=[]
    for month,a in d.groupby(level='month'):
        for label,z in [('All rows',a), ('Exclude Pb=0.50 (diagnostic)',a[a.Pb.ne(.5)]), ('Exclude Pb=0.50 and Bv<=0.10 (diagnostic)',a[a.Pb.ne(.5)&a.Bv.gt(.1)])]:
            # Ratios/differences of percentiles are order proxies only, not accounting identities.
            proxy = np.log(z.Mkt_Cap_3M_Usd) - np.log(z.Bv)
            corr = spearmanr(z.Pb, proxy).statistic if len(z)>2 else np.nan
            monthly.append(dict(month=month,formation_month=month-1,sample=label,n=len(z),spearman_pb_logrank_ratio=corr,midpoint_share=z.Pb.eq(.5).mean()))
            for control,variable,expected in [('Bv','Mkt_Cap_3M_Usd',1),('Mkt_Cap_3M_Usd','Bv',-1)]:
                bins = np.minimum((z[control]*5).astype(int),4)+1
                for b in range(1,6):
                    zz=z.loc[bins.eq(b)]
                    rho=spearmanr(zz.Pb,zz[variable]).statistic if len(zz)>2 and zz.Pb.nunique()>1 and zz[variable].nunique()>1 else np.nan
                    conditional.append(dict(month=month,sample=label,control=control,control_bin=b,n=len(zz),spearman=rho,expected_sign=expected))
    monthly=pd.DataFrame(monthly).set_index('month')
    table(monthly,'pb_sanity_monthly','Within-month Spearman between P/B rank and log(cap rank)-log(book rank). Diagnostic association, not validation of raw P/B identity.')
    c=pd.DataFrame(conditional)
    table(c,'pb_conditional_monthly','Within-month, within coarse control-rank quintile Spearman; cap association expected positive and book association negative only as qualitative diagnostics.')
    summaries=[]
    for label,z in monthly.groupby('sample',sort=False):
        v=z.spearman_pb_logrank_ratio
        summaries.append(dict(sample=label,test='Log percentile-ratio proxy',months=v.count(),median_monthly_rho=v.median(),mean_monthly_rho=v.mean(),min_monthly_rho=v.min(),max_monthly_rho=v.max(),expected_sign_share=v.gt(0).mean()))
    for (label,control),z in c.groupby(['sample','control'],sort=False):
        v=z.spearman.dropna(); sign=z.expected_sign.iloc[0]
        summaries.append(dict(sample=label,test='Within '+control+' rank quintiles',months=z.month.nunique(),median_monthly_rho=v.median(),mean_monthly_rho=v.mean(),min_monthly_rho=v.min(),max_monthly_rho=v.max(),expected_sign_share=(v*sign).gt(0).mean()))
    summary=pd.DataFrame(summaries).set_index(['sample','test'])
    table(summary,'pb_sanity_summary','Equal-weight summaries of monthly correlations (conditional tests summarize month-bin cells); no significance claim or raw-ratio reconstruction.')
    # Persist midpoint time profile and side-by-side low-book conditional diagnostic.
    mass=d.groupby(level='month').agg(n=('Pb','size'),pb_midpoint_n=('pb_midpoint_flag','sum'),bv_low_n=('bv_low_decile_flag','sum'))
    mass['formation_month']=(mass.index-1).astype(str)
    mass['midpoint_share']=mass.pb_midpoint_n/mass.n
    table(mass,'pb_midpoint_monthly','Monthly share at P/B percentile 0.50; no automatic exclusion.')
    heat=d.assign(cap_bin=np.minimum((d.Mkt_Cap_3M_Usd*5).astype(int),4)+1,bv_bin=np.minimum((d.Bv*5).astype(int),4)+1).pivot_table(index='bv_bin',columns='cap_bin',values='Pb',aggfunc='median')
    table(heat,'pb_rank_heatmap','Pooled median P/B rank by book-value and cap percentile bins: [0,.2), [.2,.4), [.4,.6), [.6,.8), [.8,1]. Composition may vary over time.')
    return frequencies,monthly,summary,mass,heat


def figures(d,m,q,freq,pb_month,summary,mass,heat):
    config.apply_style()
    t=pd.PeriodIndex(m.formation_month,freq='M').to_timestamp()
    fig,ax=utils.new_fig('full')
    ax.plot(t,m.stocks_present,label='Stocks present')
    flagged=m.count_change_flag_2pct.to_numpy()
    ax.scatter(t[flagged],m.stocks_present.to_numpy()[flagged],s=12,color=config.COLORS[3],label='Count change >=2%')
    for month,label,xytext in [('1999-06','Jun 1999', (12,16)),('2018-12','Dec 2018',(-65,-8)),('2019-02','Feb 2019',(-60,12))]:
        row=m[m.formation_month.eq(month)].iloc[0]
        ax.annotate(label,(pd.Period(month).to_timestamp(),row.stocks_present),xytext=xytext,textcoords='offset points',fontsize=7,arrowprops=dict(arrowstyle='-',lw=.6))
    ax.set(title='2A | Monthly stock counts reveal changing sample membership',ylabel='Unique securities')
    time_axis(ax);ax.legend(loc='lower center',ncol=2)
    save(fig,'stock_counts')

    fig,ax=utils.new_fig('full')
    ax.plot(t,m.coverage_present,label='Valid returns / rows present')
    ax.plot(t,m.coverage_within_observed_spells,label='Valid returns / within-spell rows',ls='--')
    ax.plot(t,m.presence_all_sample_ids,label=f'Rows present / all {d.stock_id.nunique():,} sample IDs',color=config.COLORS[1])
    ax.set_ylim(.4,1.04); ax.set(title='2A | Complete observed returns do not imply complete membership',ylabel='Coverage or presence')
    utils.percent_axis(ax);time_axis(ax);ax.legend(loc='lower left',fontsize=6.5)
    save(fig,'return_coverage','All-ID denominator uses hindsight; not investability.')

    fig,ax=utils.new_fig('full')
    ax.bar(t,m.arrivals_vs_prior_month,width=24,label='Arrivals',color=config.COLORS[0])
    ax.bar(t,-m.departures_vs_prior_month,width=24,label='Departures',color=config.COLORS[3])
    ax.set(title='2A | Membership transitions distinguish absent rows from null returns',ylabel='Securities (+ arrivals / - departures)')
    time_axis(ax);ax.legend(loc='lower left');save(fig,'membership_transitions','First-month transitions undefined; causes unobserved.')

    fig,axes=utils.new_fig('full',ncols=2)
    bins=np.r_[-1,np.linspace(-.9,1,96),np.linspace(1.2,31,60)]
    for ax in axes:
        ax.hist(d.R1M_Usd,bins=bins,color=config.COLORS[0],alpha=.6,label='Raw')
        ax.hist(d.R1M_Usd_winsor_01_99,bins=bins,histtype='step',color=config.COLORS[3],label='Monthly 1/99 clipped',linewidth=1)
        ax.set_yscale('log');ax.set_ylabel('Stock-month count (log)');ax.set_xlabel('Forward monthly return');utils.percent_axis(ax,'x')
    axes[0].set_xlim(-1,31);axes[0].set_xticks([0,10,20,30]);axes[0].set_title('Full range: maximum +3,017.6%')
    axes[1].set_xlim(-1,1);axes[1].set_title('Detail: -100% to +100%');axes[1].legend(fontsize=6)
    save(fig,'return_distribution','Detail panel zooms; full panel retains both tails.')

    fig,ax=utils.new_fig('full')
    ax.plot(t,q.return_lower_01,label='Monthly 1st percentile')
    ax.plot(t,q.return_upper_99,label='Monthly 99th percentile',color=config.COLORS[1])
    ax.axhline(0,color=config.COLOR_MARKET,lw=.5);utils.percent_axis(ax)
    ax.set(title='2A | Winsorization uses each month\'s own return cutoffs',ylabel='Forward monthly return cutoff')
    time_axis(ax);ax.legend(loc='upper left');save(fig,'winsor_cutoffs','Main rule clips 1% in each tail (central 98%).')

    fig,axes=utils.new_fig('full',ncols=2)
    counts=d.Pb.value_counts().sort_index();colors=[config.COLORS[3] if x==.5 else config.COLORS[0] for x in counts.index]
    axes[0].bar(counts.index,counts/len(d),width=.008,color=colors)
    axes[0].set(title='P/B percentile: mass at 0.50',xlabel='P/B percentile (0-1)',ylabel='Share of stock-months');utils.percent_axis(axes[0],decimals=1)
    labels=['Pb = 0.50','Other Pb']
    shares=[d.loc[d.Pb.eq(.5),'Bv'].le(.1).mean(),d.loc[d.Pb.ne(.5),'Bv'].le(.1).mean()]
    axes[1].bar(labels,shares,color=[config.COLORS[3],config.COLORS[0]],width=.55)
    axes[1].set(title='Association with low book ranks',ylabel='Share with book-value rank <=0.10',xlabel='P/B group');utils.percent_axis(axes[1]);axes[1].set_ylim(0,.75)
    save(fig,'pb_distribution','Low book rank does not reveal nonpositive book equity.')

    fig,axes=utils.new_fig('full',ncols=2)
    a=axes[0].imshow(heat,origin='lower',vmin=0,vmax=1,cmap='cividis',aspect='auto')
    axes[0].set_xticks(range(5),range(1,6));axes[0].set_yticks(range(5),range(1,6))
    axes[0].set(title='Median P/B rank',xlabel='Market-cap percentile bin (low to high)',ylabel='Book-value percentile bin (low to high)')
    axes[0].grid(False)
    for i in range(5):
        for j in range(5): axes[0].text(j,i,f'{heat.iloc[i,j]:.2f}',ha='center',va='center',fontsize=7,color='white' if heat.iloc[i,j]<.5 else 'black')
    for label,color in [('All rows',config.COLORS[0]),('Exclude Pb=0.50 (diagnostic)',config.COLORS[3])]:
        z=pb_month[pb_month['sample'].eq(label)]
        axes[1].plot((z.index-1).to_timestamp(),z.spearman_pb_logrank_ratio,label='All rows' if label=='All rows' else 'Without Pb=0.50',color=color)
    axes[1].set(title='Within-month rank association',ylabel='Spearman correlation',xlabel='Formation year',ylim=(0,1))
    axes[1].xaxis.set_major_locator(mdates.YearLocator(8));axes[1].xaxis.set_major_formatter(mdates.DateFormatter('%Y'));axes[1].legend(fontsize=6)
    save(fig,'pb_sanity','Proxy = log(cap rank) - log(book rank); not raw P/B.')


def verify(d,m,present,interior,spells):
    checks={}
    def check(name,condition):
        if not bool(condition): raise AssertionError(name)
        checks[name]='PASS'
    raw=pd.read_csv(config.FILE_PART2)
    restored=d.sort_values('source_row')
    check('all_input_rows_preserved',len(d)==len(raw))
    for col in raw.columns:
        if col!='date': check('raw_column_unchanged_'+col,np.allclose(restored[col],raw[col],equal_nan=True))
    check('raw_dates_preserved',np.array_equal(restored.formation_month.astype(str),pd.to_datetime(raw.date,format='%m/%d/%Y').dt.to_period('M').astype(str)))
    check('unique_security_formation_keys',not d.reset_index().duplicated(['stock_id','formation_month']).any())
    check('earned_month_equals_formation_plus_one',(d.index==pd.PeriodIndex(d.formation_month)+1).all())
    check('monthly_grid_contiguous',len(m)==m.index[-1].ordinal-m.index[0].ordinal+1)
    check('observed_missing_partition',(m.valid_returns+m.missing_return_rows==m.stocks_present).all())
    check('count_transition_identity',(m.stocks_present.diff().iloc[1:]==(m.arrivals_vs_prior_month-m.departures_vs_prior_month).iloc[1:]).all())
    check('arrival_partition',(m.first_seen.iloc[1:]+m.reappearances.iloc[1:]==m.arrivals_vs_prior_month.iloc[1:]).all())
    check('departure_partition',(m.departures_later_reappear.iloc[1:]+m.departures_not_seen_again.iloc[1:]==m.departures_vs_prior_month.iloc[1:]).all())
    check('spell_gaps_match_grid',spells.interior_absent_months.sum()==interior.to_numpy().sum())
    check('missing_mask_preserved',d.R1M_Usd.isna().equals(d.R1M_Usd_winsor_01_99.isna()))
    check('clipped_bounds_respected',((d.R1M_Usd_winsor_01_99>=d.return_lower_01)&(d.R1M_Usd_winsor_01_99<=d.return_upper_99)|d.return_missing).all())
    for month,z in d.groupby(level='month'):
        r=z.R1M_Usd.dropna().to_numpy()
        lo,hi=np.quantile(r,[.01,.99],method='linear')
        if not np.allclose(z.R1M_Usd_winsor_01_99,np.clip(z.R1M_Usd,lo,hi),equal_nan=True):
            raise AssertionError(f'Independent NumPy clipping failed: {month}')
    checks['independent_numpy_quantiles_all_months']='PASS'
    # Small synthetic edge case verifies clipping preserves missingness and ties.
    s=pd.Series([-1.,0.,0.,1.,np.nan]);lo,hi=s.quantile([.01,.99],interpolation='linear')
    check('synthetic_nan_and_tie_case',np.allclose(s.clip(lo,hi),[-.97,0,0,.97,np.nan],equal_nan=True))
    check('no_return_below_minus_100pct',not d.R1M_Usd.lt(-1).any())
    return checks


def write_report(d,m,q,summary,spells,checks):
    groups=TABLES['tab_2A_pb_midpoint_groups'][0]
    nclip=int(d.return_clipped_lower.sum()+d.return_clipped_upper.sum())
    gapn=int(spells.interior_absent_months.sum())
    allrho=summary.loc[('All rows','Log percentile-ratio proxy'),'median_monthly_rho']
    norho=summary.loc[('Exclude Pb=0.50 (diagnostic)','Log percentile-ratio proxy'),'median_monthly_rho']
    draft=f'''# Question 2A: findings draft

The supplied extract contains {len(d):,} stock-months for {d.stock_id.nunique():,} anonymized securities over {len(m)} formation months (November 1998-March 2019; forward returns December 1998-April 2019). Monthly counts range from {m.stocks_present.min():,} to {m.stocks_present.max():,}. Membership expands in 1999-2003, remains near 1,190 through much of 2004-2016, and contracts thereafter. Especially questionable are December 2018 (1,109 to 911 stocks, -17.9%) and February 2019 (907 to 555, -38.8%). April 1999 is also questionable: 182 IDs disappear and 166 arrive, masking large membership changes behind a net fall of only 16; all 182 departing IDs later reappear. June, September and December 1999, March 2000 and March 2001 show count jumps above 2%. These patterns require clarification of entry, exit and historical selection rules; a stable count alone cannot establish a consistently defined or survivorship-free investable universe.

Raw one-month returns range from {d.R1M_Usd.min():.1%} to {d.R1M_Usd.max():,.1%}, with a strongly asymmetric upper tail. We interpret “winsorize at the 99% level” as clipping each formation month's returns at its own 1st and 99th percentiles (linear interpolation), retaining the central 98%. This changes {nclip:,} observations ({nclip/len(d):.2%}) without deleting rows. Raw returns are retained, monthly cutoffs and every changed observation are logged, and a 0.5th/99.5th-percentile alternative is supplied because “central 99%” is another plausible reading. Extremes are not proven errors. Ex-post cross-sectional clipping changes realized outcomes and is a robustness convention, not an implementable prediction rule.

Return coverage is 100% among rows actually supplied in every month. This does not measure missing securities: {gapn:,} stock-month rows are absent inside the observed spans of {spells.interior_absent_months.gt(0).sum()} securities, and additional securities cease appearing before the sample ends. Those absences are shown separately from null return fields and are not assigned zero returns. Departures can reflect extraction, corporate events or delisting; the file cannot distinguish them. No observations or months are excluded at this stage.

The standardized P/B field is a percentile on a 0-1 scale, not an actual ratio. Exactly 0.50 accounts for {d.pb_midpoint_flag.sum():,} observations ({d.pb_midpoint_flag.mean():.2%}), compared with about 1% in a typical percentile bucket. Among these rows, {groups.loc['Pb = 0.50','bv_le_010_share']:.1%} have book-value rank at or below 0.10, versus {groups.loc['Pb != 0.50','bv_le_010_share']:.1%} elsewhere. This is consistent with a special coding or imputation rule and could relate to nonpositive book equity, but neither the sign of equity nor the reason for the midpoint mass is observable. Keep the flag and assess any later value-universe exclusion explicitly.

As an ordinal sanity check, within-month P/B ranks are positively associated with log(market-cap percentile)-log(book-value percentile): the median monthly Spearman correlation is {allrho:.3f}, or {norho:.3f} when P/B=0.50 rows are omitted for diagnosis only. Conditional rank-bin associations provide a second check. These results are compatible with the valuation relation but cannot verify P/B = Market Cap / Book Equity: percentile transformations do not preserve ratios, ties discard information, equity signs are unavailable, and the supplied market cap is a three-month average rather than necessarily the contemporaneous numerator.
'''
    (PART/'findings_2A.md').write_text(draft)
    methods='''# Question 2A: cleaning decisions and open methodological choices

## Decisions implemented

- Scope: all supplied history for 2A. No 2B-2D portfolios, performance series, benchmark joins or factor tests are computed. The assignment's later formation window is configured as December 1998-November 2018, but is not used to suppress questionable boundary months in 2A.
- Input: strict numeric schema, month-end dates, unique security/formation-month keys, finite numeric values and percentile bounds. Unexpected violations raise errors; there is no silent numeric coercion, duplicate removal or row filtering. Existing raw fields remain unchanged. The data are sorted after assigning an original source-row identifier.
- Dates: `formation_month` retains the supplied date's calendar month. The monthly Period index `month` is the earned month, exactly `formation_month + 1`, using the team date helper. Figures use explicitly labelled formation dates. Example: December 1998 formation -> January 1999 earned return. No row-wise shift, which could misalign gaps.
- Return units: decimals throughout code and CSVs. Convert to percentages only on chart axes and in prose. Summaries are pooled stock-month statistics, not strategy performance or annualized investment returns.
- Main winsorization: independent monthly nonmissing return samples, pandas linear quantiles q(.01), q(.99). With sorted returns x and h=(n-1)p, interpolate x[floor(h)] + fractional(h)*(x[ceil(h)]-x[floor(h)]). Clip only strict inequalities, retain ties at the cutoffs, preserve NaNs. “99%” is ambiguous; main rule clips 1% per tail (central 98%), while a separate sensitivity table uses 0.5% per tail (central 99%). No pooled/global cutoff and no compounded-return adjustment. The 0.5/99.5 alternative is not a second approved cleaned return field.
- Missing returns: none found in supplied rows. If future revisions have them, retain the missing mask and flag; do not interpret as zero or forward-fill. A later analysis must disclose an explicit investability/weight policy and potential outcome-based selection bias. Naive renormalization after observing missing returns can be biased.
- Membership: form the complete calendar-month by all-observed-ID grid for diagnostics only. Observed-row coverage = valid returns / supplied rows; within-spell coverage adds only missing rows between each ID's first and last observation to the denominator; full-sample presence = supplied rows / all IDs ever observed. The latter two use future information and are not point-in-time universes. An absent next-month row does not make the current forward return missing. Final sample rows are right-censored, not inferred delistings. No interior-gap rows are inserted into the cleaned data.
- Unusual months: descriptive flags use absolute monthly count change >=2%, not an error test; include earliest/latest boundary months in the narrative. Gross entry/exit counts catch changes masked by stable net counts; a second descriptive flag marks arrivals plus departures >=10% of the prior count, including April 1999. No flagged dates are excluded.
- Percentiles: keep original ranks; do not restandardize or impute. `pb_midpoint_flag` marks exact Pb=0.50 and `bv_low_decile_flag` marks Bv<=0.10. Neither proves nonpositive equity. The special-case diagnostic subsets are labelled and do not alter the cleaned sample.
- P/B sanity: monthly Spearman correlation of Pb with log(cap percentile)-log(Bv percentile), a ratio-of-ranks heuristic only. Coarse quintile conditioning checks positive cap/Pb and negative book/Pb rank associations. The quintile intervals are [0,.2), [.2,.4), [.4,.6), [.6,.8), [.8,1]. The conditional summary averages month-bin cells equally. No p-values are claimed: repeated security observations, ties and temporal dependence make naive significance misleading. A stronger sign/order check could compare cap-dominant, book-inferior pairs, but still cannot confirm accounting identity or signs.
- Scope of the source dictionary: https://www.mlfactor.com/data-description.html defines Pb as price to book, Bv as book value, R1M_Usd as forward one-month return, and Mkt_Cap_3M_Usd as three-month average market cap. It does not establish that 0.50 is a nonpositive-equity or missing-value sentinel. Assignment and team files govern forward dates, decimal units and 0-1 scaling.

## Unresolved choices affecting 2B-2D (for team review before implementation)

1. Confirm whether the instructor intends 1/99 or 0.5/99.5 monthly winsorization; agree raw versus clipped return robustness reporting. Clipping can change market/value returns and their correlations, especially in crisis months. Monthly realized-return cutoffs are available ex post.
2. Determine the provenance of Pb=0.50 (imputation, ties, special treatment of negative equity, or another cause). Obtain raw book-equity signs or vendor metadata if possible. If metadata confirms nonpositive book equity, exclude those confirmed cases from a positive-book value ranking and disclose the comparison-universe policy. Compare retain-all versus flagged exclusion as a later value-universe sensitivity; applying a strict exclusion now would discard valid median-ranked stocks and is not justified by these data alone.
3. Decide how to map P/B ranks to book-to-price exposure. For positive raw equity, reversing P/B ordering is defensible; taking 1/Pb on percentile values does not recover raw B/P. Choice of 1-Pb versus reversed within-month percentile rank and handling zero weights/ties matters, particularly for the top 20% cutoff and midpoint mass. No mapping chosen in 2A.
4. Clarify why the historical membership expands then contracts, particularly December 2018 and February 2019; establish whether historical selection/survivorship and point-in-time accounting availability can be verified. The later 2B formation window stops in November 2018 (return December 2018), but that does not resolve earlier selection or last-period forward-return reliability. Do not condition eligibility on future persistence or balance the panel.
5. Agree how to handle absent security-month rows, any future missing returns, mergers and delistings, including terminal proceeds. Do not infer a -100% delisting return, cash return or zero from disappearance. Any weight renormalization needs an explicit rule and bias assessment. Current observed rows have no null returns.
6. Recognize percentile cap weights are only the assignment's approximation; normalized rank weights are not actual capitalization weights. Align HML and MSCI USA on earned months and compare shared-loader reference values with teammates when 2B-2D begin (not performed here). Confirm gross/net dividends, USD and source universes before interpretation.
7. Keep the specified later window and decimal units, agree arithmetic versus geometric return summaries, common eligibility across benchmark/value comparisons, tie allocation for top-20% portfolios, and whether exclusion requires recomputing within-month value ranks. None of these later strategy choices is silently resolved in 2A.

## Reading and validation record

Read before implementation: both PDFs in `Read it before you do!/`, `README.md`, `src/config.py`, `src/utils.py`, and `part2/README.md`. Assignment 2A is on pages 4-5; all five bullets are covered. Shared code is imported for style, dates, figures and tables. The raw input SHA-256, package versions, base Git revision, missingness, and verification results are saved in `validation_2A.json`. Raw data/shared code/other members' folders are unchanged. No commits or pushes are made.
'''
    (PART/'methodology_2A.md').write_text(methods)
    catalog=pd.DataFrame([dict(file=k+'.csv',description=v[1]) for k,v in TABLES.items()])
    utils.save_table(catalog,'tab_2A_catalog')
    # Human-readable companion for publication: key tables, all figures, source notes.
    report=['<!doctype html><html lang="en"><meta charset="utf-8"><title>FE5108 Question 2A review</title>',
    '<style>body{font:14px Arial,sans-serif;color:#222;max-width:1000px;margin:40px auto;line-height:1.5}h1{font-size:24px}h2{font-size:18px;margin-top:32px}figure{margin:24px 0;break-inside:avoid}img{width:6in;max-width:100%;height:auto}table{border-collapse:collapse;font-size:12px;width:100%;margin:12px 0}th,td{padding:7px;border-bottom:1px solid #ddd;text-align:right}th{background:#edf3f6}td:first-child,th:first-child{text-align:left}p.note{font-size:11px;color:#555}pre{white-space:pre-wrap} @media print{body{margin:0}figure{page-break-inside:avoid}}</style>',
    '<h1>FE5108 | Question 2A: Data Cleaning and Validation</h1><p>Review draft. All supplied stock-month rows retained. No work on Questions 2B-2D.</p>',
    '<h2>Findings draft</h2>']
    for p in draft.split('\n\n')[1:]: report.append('<p>'+html.escape(p)+'</p>')
    for f in FIGURES:
        report.append(f'<figure><img src="../output/figures/{f}.png" alt="{f}"></figure>')
    for key in ['return_summary','winsor_interpretation_sensitivity','unusual_months','pb_midpoint_groups','pb_sanity_summary']:
        name='tab_2A_'+key;df,desc=TABLES[name]
        if key=='unusual_months':df=df[['formation_month','stocks_present','stock_count_change','arrivals_vs_prior_month','departures_vs_prior_month']]
        if key=='return_summary':df=df[['count','mean','std','min','1%','50%','99%','max','skewness']]
        if key=='pb_sanity_summary':df=df[['median_monthly_rho','min_monthly_rho','max_monthly_rho','expected_sign_share']]
        report.append('<h2>'+html.escape(key.replace('_',' ').title())+'</h2>'+df.to_html(float_format=lambda x:f'{x:,.4f}')+'<p class="note">'+html.escape(desc)+' Source: supplied Part 2 CSV; all supplied securities, formation Nov 1998-Mar 2019 / earned Dec 1998-Apr 2019, except explicitly labelled diagnostic subsets. Return values are decimals.</p>')
    report.append('<h2>Cleaning decisions and unresolved choices</h2><pre>'+html.escape(methods)+'</pre><h2>Verification</h2><pre>'+html.escape(json.dumps(checks,indent=2))+'</pre></html>')
    (PART/'review_2A.html').write_text('\n'.join(report))


def main():
    d=load()
    m,present,interior,spells=membership(d)
    d,q=winsorize(d)
    freq,pb_month,summary,mass,heat=pb_checks(d)
    figures(d,m,q,freq,pb_month,summary,mass,heat)
    checks=verify(d,m,present,interior,spells)
    clean=PART/'data_cleaned_2A.csv.gz'
    # Round-trip safe decimal precision; compression header fixed for reproducible file hashes.
    d.to_csv(clean,float_format='%.17g',compression={'method':'gzip','mtime':0})
    import subprocess
    base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    validation=dict(input_sha256=hashlib.sha256(config.FILE_PART2.read_bytes()).hexdigest(),base_git_revision=base,
        rows=len(d),securities=d.stock_id.nunique(),formation_months=len(m),
        missing_by_raw_column=pd.read_csv(config.FILE_PART2).isna().sum().to_dict(),
        lower_clipped=int(d.return_clipped_lower.sum()),upper_clipped=int(d.return_clipped_upper.sum()),
        versions={'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__,'matplotlib':matplotlib.__version__,'scipy':scipy.__version__},checks=checks)
    (PART/'validation_2A.json').write_text(json.dumps(validation,indent=2))
    write_report(d,m,q,summary,spells,checks)
    print(json.dumps(validation,indent=2))

if __name__=='__main__':
    main()
