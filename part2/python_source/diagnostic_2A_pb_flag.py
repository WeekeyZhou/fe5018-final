"""Additive 2A diagnostic. Does not rerun or overwrite existing 2A results.
Run: python part2/python_source/diagnostic_2A_pb_flag.py
"""
from pathlib import Path
import hashlib
import json
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src import config, utils

PART = ROOT / 'part2'
FLAG = 'pb_midpoint_low_bv_provisional_flag'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    original = PART / 'data_cleaned_2A.csv.gz'
    original_sha = sha(original)
    raw_sha = sha(config.FILE_PART2)
    d = pd.read_csv(original, float_precision='round_trip')
    if FLAG in d.columns:
        raise ValueError('Expected original 2A file without new flag.')
    flag = d.Pb.eq(.50) & d.Bv.le(.03)
    rows = []
    for bv in [.01, .02, .03, .04]:
        z = d.loc[d.Bv.eq(bv)]
        n = len(z)
        hits = int(z.Pb.eq(.50).sum())
        rows.append(dict(Bv=bv, n_stock_months=n, n_pb_eq_050=hits,
                         n_pb_ne_050=n-hits,
                         frequency_pb_eq_050_given_bv=hits/n if n else float('nan'),
                         n_distinct_securities=z.stock_id.nunique(),
                         n_formation_months=z.formation_month.nunique()))
    summary = pd.DataFrame(rows).set_index('Bv')
    utils.save_table(summary, 'tab_2A_pb_conditional_low_bv', float_format='%.10g')
    # A separate enriched copy preserves all original columns and rows exactly.
    enriched = d.assign(**{FLAG:flag})
    newfile = PART / 'data_cleaned_2A_with_provisional_pb_flag.csv.gz'
    enriched.to_csv(newfile, index=False, float_format='%.17g', compression={'method':'gzip','mtime':0})
    monthly = enriched.groupby(['month','formation_month'],sort=True).agg(
        n_stock_months=('stock_id','size'), n_flagged=(FLAG,'sum'))
    monthly['flagged_share'] = monthly.n_flagged / monthly.n_stock_months
    utils.save_table(monthly,'tab_2A_pb_provisional_flag_monthly',float_format='%.10g')
    totals = pd.DataFrame([dict(n_stock_months=len(d), n_flagged=int(flag.sum()),
                               flagged_share=flag.mean(), n_flagged_securities=d.loc[flag,'stock_id'].nunique(),
                               n_pb_midpoint=int(d.Pb.eq(.50).sum()),
                               flagged_share_of_pb_midpoint=flag.sum()/d.Pb.eq(.50).sum())])
    utils.save_table(totals,'tab_2A_pb_provisional_flag_summary',float_format='%.10g')
    # Independently check serialized data and the requested conditional denominator.
    back = pd.read_csv(newfile, float_precision='round_trip')
    pd.testing.assert_frame_equal(back.drop(columns=FLAG), d)
    pd.testing.assert_series_equal(back[FLAG], flag.rename(FLAG))
    raw = pd.read_csv(config.FILE_PART2)
    for bv in summary.index:
        sub = raw[raw.Bv.eq(bv)]
        assert len(sub) == summary.loc[bv,'n_stock_months']
        assert sub.Pb.eq(.5).sum() == summary.loc[bv,'n_pb_eq_050']
    assert len(back) == len(raw)
    assert monthly.n_flagged.sum() == flag.sum()
    assert flag.sum() == summary.loc[[.01,.02,.03],'n_pb_eq_050'].sum()
    assert not (back[FLAG] & back.Bv.eq(.04)).any()
    assert sha(original) == original_sha and sha(config.FILE_PART2) == raw_sha
    validation = dict(original_cleaned_sha256=original_sha,raw_sha256=raw_sha,
                      rows=len(back),flagged=int(flag.sum()),
                      checks={'serialized_existing_columns_unchanged':'PASS','all_rows_retained':'PASS',
                              'serialized_flag_matches_definition':'PASS','counts_match_independent_raw_data':'PASS',
                              'monthly_flag_counts_reconcile':'PASS','flag_matches_first_three_bv_buckets':'PASS',
                              'bv_004_never_flagged':'PASS','input_files_unchanged':'PASS'})
    (PART/'validation_2A_pb_flag.json').write_text(json.dumps(validation,indent=2))
    lines=['# 2A addendum: P/B midpoint conditional on low book-value ranks','',
           'Source: supplied Part 2 CSV (mlfactor extract), all supplied securities; formation November 1998-March 2019, earned returns December 1998-April 2019. Counts pool stock-month observations; repeated observations of one security are not independent trials.','',
           '| Bv percentile | Stock-months with this Bv | Pb=0.50 stock-months | P(Pb=0.50 given Bv) |',
           '|---:|---:|---:|---:|']
    for bv,row in summary.iterrows():
        lines.append(f'| {bv:.2f} | {int(row.n_stock_months):,} | {int(row.n_pb_eq_050):,} | {row.frequency_pb_eq_050_given_bv:.2%} |')
    lines += ['',
      'The denominator in each row is all observations at that exact Bv value, not all Pb=0.50 observations. CSV frequencies are fractions on a 0-1 scale. Values are compared on the supplied two-decimal percentile grid; no rounding or reranking is applied. The separate monthly table records the flag prevalence through time.', '',
      '## Provisional definition and rationale','',
      f'`{FLAG} = (Pb == 0.50) & (Bv <= 0.03)`.', '',
      f'The flag marks {int(flag.sum()):,} of {len(d):,} stock-months ({flag.mean():.2%}), spanning {d.loc[flag,"stock_id"].nunique():,} distinct securities. It is observation-specific: a security can be flagged in one month and unflagged in another. It does not permanently classify a security.', '',
      'The combination of an unusual P/B midpoint mass and very low book-value ranks motivates a targeted diagnostic of possible special coding, imputation, or treatment of economically problematic book equity. The 0.04 bucket is included as an adjacent comparison and is not flagged. The <=0.03 boundary is a provisional, user-specified diagnostic threshold, not an estimated equity-sign boundary or an optimized investment rule.', '',
      '## Limitations and later 2C sensitivity design','',
      '- Bv and Pb are transformed percentiles, not raw equity or valuation ratios. A low Bv rank cannot establish zero or negative equity, and Pb=0.50 may include legitimate median-ranked stocks. The flag is not a confirmed nonpositive-equity or missing-data indicator.',
      '- Rounded ranks and ties lose information; historical standardization and imputation rules are unavailable. The pooled associations may reflect changing composition and repeated security observations. They do not establish a causal explanation or validate an exclusion rule.',
      '- For a later 2C sensitivity, compare the retain-all baseline with an explicitly labelled variant omitting flagged stock-months from value eligibility. Keep the same earned-month alignment, return cleaning, factor mapping, and other portfolio rules. Renormalize eligible weights explicitly and disclose how ties and within-month reranking are treated; report flagged and eligible counts by month.',
      '- Decide in advance whether the broad-market comparison remains unchanged or uses matching eligibility. Any changed performance would combine altered value exposure, size/composition, and concentration; it would not prove that flagged observations are erroneous. Apply the rule using formation-month fields only, without conditioning on forward returns or future persistence.',
      '- Seek vendor metadata or raw equity signs before interpreting the flag as an economic classification. Threshold robustness (including the adjacent 0.04 bucket) may be examined later, but do not select thresholds to maximize backtested returns.', '',
      '## Preservation and reproduction','',
      'No observations are deleted, returns are not recleaned, and the original `data_cleaned_2A.csv.gz`, original 2A script, findings, tables and figures remain unchanged. The enriched file `data_cleaned_2A_with_provisional_pb_flag.csv.gz` contains all original columns and rows plus the Boolean flag. It is a separate diagnostic copy, not a replacement approved dataset. Shared source files and raw data are unchanged. No 2C sensitivity portfolios are computed here.', '',
      'Run `python part2/python_source/diagnostic_2A_pb_flag.py` from the repository root (or use its absolute path). It uses the existing 2A environment and shared table saver without modifying shared files. Outputs are three new `tab_2A_pb_*` CSV tables, the enriched data copy, this addendum, and `validation_2A_pb_flag.json`. The original table catalog is retained unchanged; these new tables are listed here:', '',
      '- `output/tables/tab_2A_pb_conditional_low_bv.csv`: four conditional frequencies and counts.',
      '- `output/tables/tab_2A_pb_provisional_flag_summary.csv`: overall flag count, share, and security count.',
      '- `output/tables/tab_2A_pb_provisional_flag_monthly.csv`: monthly flag prevalence with earned and formation labels.', '',
      'Validation: serialized enriched data match every original cleaned column exactly; conditional counts independently reconcile to the raw CSV; flag totals reconcile across the first three Bv buckets and monthly tables; Bv=0.04 is never flagged; input hashes are unchanged. No commits or pushes.']
    (PART/'addendum_2A_pb_flag.md').write_text('\n'.join(lines)+'\n')
    print(summary.to_string())
    print(totals.to_string(index=False))
    print(json.dumps(validation,indent=2))

if __name__ == '__main__':
    main()
