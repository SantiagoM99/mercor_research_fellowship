#!/usr/bin/env python3
"""Plot every planned call, keeping missing outputs distinct from wrong verdicts."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]

def main():
    models=json.loads((ROOT/'analysis/boundary-format-v1.json').read_text())['models']
    fig,ax=plt.subplots(figsize=(8.6,3.4))
    colors=['#447ca7','#df6b45','#bbb8b1']
    labels=[]
    y=3
    for model in models:
        for condition in model['conditions']:
            valid=condition['valid'];wrong=condition['errors'];missing=condition['unresolved'];n=condition['planned']
            left=0
            for count,color in zip([valid-wrong,wrong,missing],colors):
                width=100*count/n
                ax.barh(y,width,left=left,color=color,height=.58)
                if count: ax.text(left+width/2,y,str(count),ha='center',va='center',color='white' if color!=colors[2] else '#222',fontsize=10)
                left+=width
            labels.append((y,model['model']+' · '+condition['notation']))
            y-=1
    ax.set_yticks([y for y,label in labels]);ax.set_yticklabels([label for y,label in labels],fontsize=10)
    ax.set_xlim(0,100);ax.set_xlabel('Share of the 96 planned calls per condition (%)')
    ax.set_title('Equivalent notation, different grading outcomes',loc='left',fontsize=13,pad=14)
    ax.legend([plt.Rectangle((0,0),1,1,color=c) for c in colors],['Correct verdict','Wrong verdict','No valid verdict'],
        loc='upper center',bbox_to_anchor=(.5,-.2),ncol=3,frameon=False)
    for sp in ['top','right','left']:ax.spines[sp].set_visible(False)
    ax.spines['bottom'].set_color('#ccc');ax.tick_params(axis='y',length=0)
    fig.tight_layout()
    for ext in ['png','pdf','svg']:
        out=ROOT/'figures'/f'boundary_format.{ext}'
        fig.savefig(out,dpi=220,bbox_inches='tight',facecolor='white')
        if ext=='svg':out.write_text('\n'.join(line.rstrip() for line in out.read_text().splitlines())+'\n')
    plt.close(fig)
    print('Saved figures/boundary_format.{png,pdf,svg}')

if __name__=='__main__':main()
