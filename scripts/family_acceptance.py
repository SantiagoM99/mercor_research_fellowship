#!/usr/bin/env python3
"""Conservative family-event acceptance bound and a reproducible coverage study."""
import argparse
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'experiments/family-acceptance-v1.json'


def binomial_cdf(k,n,p):
    if k < 0: return 0.0
    if k >= n or p == 0: return 1.0
    if p == 1: return 0.0
    return min(1.0,math.fsum(math.exp(math.lgamma(n+1)-math.lgamma(j+1)-math.lgamma(n-j+1)
        +j*math.log(p)+(n-j)*math.log1p(-p)) for j in range(k+1)))


@lru_cache(maxsize=None)
def upper_bound(k,n,alpha=.05):
    if not isinstance(k,int) or not isinstance(n,int) or n<0 or not 0<=k<=n or not 0<alpha<1:
        raise ValueError('Require integers 0 <= k <= n and 0 < alpha < 1')
    if n==0 or k==n: return 1.0
    if k==0: return -math.expm1(math.log(alpha)/n)
    low,high=0.0,1.0
    for _ in range(60):
        mid=(low+high)/2
        if binomial_cdf(k,n,mid)>alpha: low=mid
        else: high=mid
    return high


def family_bound(error_counts,eligible_counts,comparisons=6,alpha=.05):
    if len(error_counts)!=len(eligible_counts) or comparisons<1:
        raise ValueError('Invalid family counts or comparison count')
    eligible=[]
    for e,n in zip(error_counts,eligible_counts):
        if type(e) is not int or type(n) is not int or not 0<=e<=n:
            raise ValueError('Invalid count within a family')
        if n: eligible.append((e,n))
    return dict(eligible_families=len(eligible),
        mean_family_error=sum(e/n for e,n in eligible)/len(eligible) if eligible else None,
        families_with_any_error=sum(e>0 for e,n in eligible),
        upper_error_bound=upper_bound(sum(e>0 for e,n in eligible),len(eligible),alpha/comparisons),
        comparisons=comparisons,assumption='independent identically sampled eligible families; fixed judge and sampling/labeling rules')


def zero_error_sample(limit,comparisons=6,alpha=.05):
    return math.ceil(math.log(alpha/comparisons)/math.log1p(-limit))


def critical_count(n,p,alpha):
    """Largest error count whose exact upper bound is below p; -1 means never."""
    low,high=-1,n
    while high-low>1:
        mid=(low+high)//2
        if binomial_cdf(mid,n,p)<alpha: low=mid
        else: high=mid
    return low


def run():
    import numpy as np
    config=dict(study_id='family-acceptance-v1',seed=20260913,replications=5000,
        family_counts=[16,45,150],criteria_per_family=10,true_rates=[.01,.02,.05,.10],
        dependence=['independent','perfectly_correlated'],alpha=.05,comparisons=6,
        refutation='Any unadjusted family-event undercoverage above 6% stops adoption pending investigation',
        scope='Simulated labels for implementation and precision; not model judgments or empirical Mercor evidence')
    if CONFIG.exists():
        if json.loads(CONFIG.read_text())!=config: raise ValueError('Frozen configuration changed')
    else: CONFIG.write_text(json.dumps(config,indent=2)+'\n')
    rng=np.random.default_rng(config['seed']); rows=[]
    for n in config['family_counts']:
        for p in config['true_rates']:
            for dependence in config['dependence']:
                if dependence=='independent':
                    counts=rng.binomial(10,p,size=(5000,n)); event_p=-math.expm1(10*math.log1p(-p))
                else:
                    counts=rng.binomial(1,p,size=(5000,n))*10; event_p=p
                event_count=(counts>0).sum(axis=1); total=counts.sum(axis=1)
                rows.append(dict(families=n,true_mean_error=p,dependence=dependence,replications=5000,
                    family_event_risk=event_p,
                    naive_pooled_undercoverage=float(np.mean(total<=critical_count(n*10,p,.05))),
                    family_event_undercoverage=float(np.mean(event_count<=critical_count(n,event_p,.05))),
                    family_mean_undercoverage=float(np.mean(event_count<=critical_count(n,p,.05))),
                    adjusted_family_mean_undercoverage=float(np.mean(event_count<=critical_count(n,p,.05/6)))))
    zero=[dict(families=n,comparisons=k,upper_error_bound=upper_bound(0,n,.05/k))
          for n in [16,45,150,237] for k in [1,6]]
    samples=[dict(error_limit=p,comparisons=k,minimum_error_free_families=zero_error_sample(p,k)) for p in [.02,.05] for k in [1,6,24]]
    output=dict(config=config,code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        scenarios=rows,zero_error_bounds=zero,minimum_samples=samples,
        simulation_check_passed=all(r['family_event_undercoverage']<=.06 for r in rows),
        limitation='Coverage argument requires independent family sampling and correct labels. Monte Carlo scenarios do not establish these assumptions for APEX.')
    (ROOT/'analysis/family-acceptance-v1.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps(dict(scenarios=len(rows),replications_per_scenario=5000,
        max_family_event_undercoverage=max(r['family_event_undercoverage'] for r in rows),
        max_naive_undercoverage=max(r['naive_pooled_undercoverage'] for r in rows),
        zero_error_45_families_six_tests=upper_bound(0,45,.05/6),minimum_samples=samples,
        simulation_check_passed=output['simulation_check_passed']),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['run'])
    parser.parse_args();run()
