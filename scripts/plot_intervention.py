#!/usr/bin/env python3
"""Export an observed before/after figure only when the full study is complete."""
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.mplconfig'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    data=json.loads((ROOT/'analysis/numeric-intervention-v1.json').read_text())
    if not data['complete'] or any(m['valid']!=m['planned'] for m in data['models']):
        raise ValueError('Refusing to plot an incomplete intervention')
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'pdf.fonttype':42,'svg.fonttype':'none'})
    labels=[]; rows=[]
    for model in data['models']:
        lookup={(r['arm'],r['language']):r for r in model['rates'] if r['task_id']=='all'}
        for language in ['en','es']:
            labels.append(f"{model['model']} · {language.upper()}")
            rows.append([lookup[(arm,language)] for arm in ['original','clarified']])
    fig,ax=plt.subplots(figsize=(9.2,4.8))
    y=np.arange(len(rows))
    for j,(label,color) in enumerate([('Original prompt','#64748b'),('Numeric clarification','#087e8b')]):
        pos=y+(j-.5)*.28
        rates=[r[j] for r in rows]
        ax.barh(pos,[100*r['error_rate'] for r in rates],height=.25,color=color,label=label)
        for p,r in zip(pos,rates):
            ax.text(100*r['error_rate']+1,p,f"{r['errors']}/{r['valid']}",va='center',fontsize=11,color='#253347')
    ax.set(yticks=y,yticklabels=labels,xlim=(0,112),xticks=[0,25,50,75,100],xlabel='Judgments inconsistent with the numeric rule (%)')
    ax.invert_yaxis();ax.spines[['top','right']].set_visible(False)
    ax.set_axisbelow(True);ax.grid(axis='x',alpha=.15)
    ax.legend(loc='lower right',frameon=False,fontsize=10)
    fig.suptitle('Does numeric-rule clarification transfer to new tasks?',fontsize=16,fontweight='bold',color='#253347',y=.97)
    fig.text(.5,.86,'2 local models · 3 new public task probes · EN/ES · original vs. clarified prompt',ha='center',fontsize=10.5)
    fig.subplots_adjust(left=.27,right=.96,top=.78,bottom=.25)
    fig.text(.03,.12,'360 observed judgments · 3 repeats per cell · lower is better; counts are errors / judgments',fontsize=10)
    fig.text(.03,.06,'Selected numeric snippets; expert review pending. Repeated calls are not independent tasks.',fontsize=10,color='#52677e')
    output=ROOT/'figures/numeric_intervention'
    for suffix in ['png','pdf','svg']:
        fig.savefig(output.with_suffix('.'+suffix),dpi=220,facecolor='white')
    plt.close(fig)
    output.with_suffix('.md').write_text('Observed prompt intervention on three selected public tasks not used in prior judge runs: 145 C2, 1122 C1 and 2205 C1. Each bar contains 45 judgments (five values × three criteria × three repeats) in one language. Original and clarified conditions receive identical responses/rubrics; the clarification is a frozen English numeric-rule amendment. Two models and two languages give 360 calls. These are numeric snippets and design predicates, not human gold labels or professional task scores. Language review remains pending. See analysis/numeric-intervention-v1.json and the full report for error classes, task-level outcomes and regressions.\n')
    print(output)


if __name__=='__main__': main()
