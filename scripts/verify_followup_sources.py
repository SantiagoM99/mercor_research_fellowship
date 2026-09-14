#!/usr/bin/env python3
"""Reproduce the follow-up advertising and NPS targets from pinned public CSVs."""
import csv
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from numeric_intervention import bounds

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/apex-v1-extended'


def number(value):
    return Decimal(value.replace(',','').replace('$','').strip())


def advertising(rows):
    rows=[{k.strip():v for k,v in r.items()} for r in rows]
    fixed=[r for r in rows if r['Payment_Method']=='Fixed Price']
    cost=sum(number(r['Payment ($)']) for r in fixed)
    impressions=sum(number(r['Total_Impressions']) for r in fixed)
    if cost<=0: raise ValueError('No positive fixed-price cost')
    return dict(campaigns=len(fixed),total_cost=str(cost),total_impressions=str(impressions),
                value=impressions/cost,method='Total impressions divided by total fixed-price campaign cost; not an unweighted mean of campaign ratios.')


def nps(rows):
    group=[r for r in rows if r['Generation']=='Gen Z']
    if not group: raise ValueError('No Gen Z records')
    scores=[int(r['Likelihood_to_Recommend']) for r in group]
    if any(x<0 or x>10 for x in scores): raise ValueError('Invalid recommendation score')
    promoters=sum(x>=9 for x in scores)
    detractors=sum(x<=6 for x in scores)
    return dict(respondents=len(scores),promoters=promoters,detractors=detractors,
                passives=len(scores)-promoters-detractors,
                value=Decimal(100)*(promoters-detractors)/len(scores),
                method='100 × (promoters minus detractors) / all Gen Z respondents, including passives; round final score only.')


def main():
    manifest=json.loads((DATA/'manifest.json').read_text())
    with (DATA/'train.csv').open(newline='') as stream:
        tasks={r['Task ID']:r for r in csv.DictReader(stream)}
    results=[]
    for task,cid,name,compute,digits in [('145',2,'Campaign_Portfolio.csv',advertising,'0.01'),('1122',1,'Survey.csv',nps,'1')]:
        source=f'documents/{task}/{name}'
        payload=(DATA/source).read_bytes()
        digest=hashlib.sha256(payload).hexdigest()
        if digest!=manifest['files'][source]['sha256']: raise ValueError('Source checksum changed')
        with (DATA/source).open(newline='',encoding='utf-8-sig') as stream:
            result=compute(list(csv.DictReader(stream)))
        lo,hi=bounds(json.loads(tasks[task]['Rubric JSON'])[f'criterion {cid}']['description'])
        submitted=result['value'].quantize(Decimal(digits),rounding=ROUND_HALF_UP)
        result.update(task_id=task,criterion_id=cid,source=source,source_sha256=digest,
            value=str(result['value']),submitted=str(submitted),accepted_bounds=[str(lo),str(hi)],
            numeric_pass=lo<=submitted<=hi)
        results.append(result)
    output=dict(dataset_revision=manifest['revision'],results=results,
        timing='Independent source checks performed during the intervention run; frozen stimuli and labels unchanged.',
        limitation='Reproduces two scalar targets only. Does not validate translations or complete professional deliverables. Bond yield target 2205 remains rubric-based.')
    (ROOT/'analysis/followup_source_checks.json').write_text(json.dumps(output,indent=2)+'\n')
    if not all(r['numeric_pass'] for r in results): raise ValueError('Target reproduction failed')
    print(json.dumps(output,indent=2))


if __name__=='__main__': main()
