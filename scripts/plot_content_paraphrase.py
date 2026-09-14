#!/usr/bin/env python3
"""Export equal-task summary bars with individual task points; observed data only."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT/'.mplconfig'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np


def main():
    data = json.loads((ROOT/'analysis/content-paraphrase-v1.json').read_text())
    if not data['complete'] or any(m['valid'] != m['planned'] for m in data['models']):
        raise ValueError('Refusing to plot an incomplete study')
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'pdf.fonttype': 42, 'svg.fonttype': 'none'})
    entries = [(m, lang) for m in data['models'] for lang in ['en', 'es']]
    fig, axes = plt.subplots(1, 2, figsize=(12.6, 6), sharey=True)
    task_colors = {'145': '#e69f00', '1122': '#7c3aed', '2287': '#0369a1'}
    y = np.arange(len(entries))
    for ax, metric, title, color in zip(axes, ['content', 'paraphrase'],
            ['Detects the substantive correction\nHigher is better', 'Changes verdict after rubric paraphrase\nLower is better'],
            ['#168579', '#64748b']):
        for i, (m, lang) in enumerate(entries):
            r = next(r for r in m['rates'] if r['task_id'] == 'equal_task_macro' and r['language'] == lang)
            pct = 100*r[metric+'_rate']
            ax.barh(i, pct, height=.48, color=color, alpha=.65)
            ax.text(103, i, f"{pct:.1f}%", va='center', fontsize=11, fontweight='bold')
            for j, (task, tcolor) in enumerate(task_colors.items()):
                tr = next(r for r in m['rates'] if r['task_id'] == task and r['language'] == lang)
                ax.scatter(100*tr[metric+'_rate'], i+(j-1)*.13, color=tcolor, edgecolor='white',
                           linewidth=.7, s=48, zorder=3, label=f'Task {task}' if i == 0 else None)
        ax.set(xlim=(-4, 122), xticks=[0, 25, 50, 75, 100], xlabel='Equal-task mean (%)', title=title)
        ax.spines[['top', 'right', 'left']].set_visible(False)
        ax.grid(axis='x', alpha=.15); ax.set_axisbelow(True)
        ax.tick_params(axis='y', length=0)
    axes[0].set(yticks=y, yticklabels=[f"{m['model']}\nResponse: {lang.upper()}" for m, lang in entries])
    axes[0].invert_yaxis()
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(.5, .19), ncol=3, frameon=False)
    fig.suptitle('Do judges track corrections and ignore paraphrases?', fontsize=19, fontweight='bold', y=.98, color='#203044')
    fig.text(.5, .895, '576 judgments · Qwen 4B + Gemma 4B · response EN/ES × grading EN/ES × original/paraphrased rubric',
             ha='center', fontsize=10.5)
    fig.subplots_adjust(left=.17, right=.97, top=.75, bottom=.31, wspace=.20)
    fig.text(.04, .145, 'Bars: equal weight per task. Dots: task rates. Each row/panel pools 24 pairs: 4 + 4 + 16 across the three tasks.', fontsize=10)
    fig.text(.04, .098, 'One verdict per cell = majority of 3 repeats; repeats are not independent tasks. See the report for counts and grading-language detail.', fontsize=9.5)
    fig.text(.04, .05, 'Selected numeric snippets and conservative paraphrases; independent human review pending. No population-level claim.', fontsize=10, color='#52677e')
    output = ROOT/'figures/content_paraphrase'
    for suffix in ['png', 'pdf', 'svg']:
        fig.savefig(output.with_suffix('.'+suffix), dpi=220, facecolor='white')
    plt.close(fig)
    output.with_suffix('.md').write_text(
        'Observed results of content-paraphrase-v1. Each bar averages rates within each source task, '
        'then equally across tasks 145, 1122 and 2287. Each response-language row contains 24 '
        'matched pairs per panel (4, 4 and 16 by task), based on three-repeat majority verdicts. '
        'Content detection requires incorrect=0 and correct=1. Paraphrase changes compare original '
        'and paraphrased rubrics with the same response and grading language. Both grading languages '
        'are included. Dots show individual task rates, not confidence intervals. The three selected '
        'public development tasks are not a representative sample. Human equivalence review pending. '
        'Full analysis: analysis/content-paraphrase-v1.json.\n')
    print(output)
    # All preplanned content pairs, including zero effects, for diagnostic review.
    rows = [('145', 2, 'Impressions per dollar'), ('1122', 1, 'Gen Z NPS'),
            ('2287', 1, 'IRR'), ('2287', 2, 'MOIC'), ('2287', 3, 'NPV at 10%'), ('2287', 5, 'NPV at 20%')]
    columns = [(lang, grading, wording) for lang in ['en', 'es'] for grading in ['en', 'es']
               for wording in ['original', 'paraphrase']]
    fig, axes = plt.subplots(1, 2, figsize=(12.6, 5.6), sharey=True)
    for ax, model in zip(axes, data['models']):
        lookup = {(p['task_id'], p['criterion_id'], p['language'], p['grading_language'], p['wording']): p['detected']
                  for p in model['pairs'] if p['kind'] == 'content'}
        matrix = np.array([[lookup[(task, cid, lang, grading, wording)] for lang, grading, wording in columns]
                           for task, cid, _ in rows])
        ax.imshow(matrix, cmap=ListedColormap(['#eed8cd', '#168579']), vmin=0, vmax=1, aspect='auto')
        for i in range(len(rows)):
            for j in range(len(columns)):
                ax.text(j, i, str(matrix[i, j]), ha='center', va='center', color='white' if matrix[i, j] else '#803f22', fontsize=12)
        ax.set(xticks=range(len(columns)), xticklabels=[f'{a.upper()}/{b.upper()}\n{"O" if c == "original" else "P"}' for a, b, c in columns],
               yticks=range(len(rows)), yticklabels=[f'{a} C{b}: {c}' for a, b, c in rows], title=model['model'])
        ax.tick_params(length=0, labelsize=9)
        ax.set_xticks(np.arange(-.5, len(columns), 1), minor=True)
        ax.set_yticks(np.arange(-.5, len(rows), 1), minor=True)
        ax.grid(which='minor', color='white', linewidth=1)
        ax.tick_params(which='minor', length=0)
    fig.suptitle('Which content corrections does each judge detect?', fontsize=17, fontweight='bold', y=.97)
    fig.subplots_adjust(left=.21, right=.98, top=.84, bottom=.24, wspace=.1)
    fig.text(.04, .12, 'Columns: response language / grading language; O = original rubric, P = paraphrase.', fontsize=10)
    fig.text(.04, .07, '1 = rejects incorrect AND accepts correct; 0 = any other verdict pair. Each verdict uses 3-repeat majority.', fontsize=10)
    fig.text(.04, .025, 'Six selected criteria on three public development tasks. Independent human review pending.', fontsize=10, color='#52677e')
    detail = ROOT/'figures/content_paraphrase_detail'
    for suffix in ['png', 'pdf', 'svg']:
        fig.savefig(detail.with_suffix('.'+suffix), dpi=220, facecolor='white')
    plt.close(fig)
    detail.with_suffix('.md').write_text('All 48 content-detection pairs per model from the frozen content-paraphrase-v1 plan. '
        'A 1 requires rejecting the incorrect response and accepting the correct response, each by majority of three repeats. '
        'A 0 includes approving both, rejecting both or reversed labels. Columns cross response language, grading language '
        'and original/paraphrased rubric. These are six criteria on three previously inspected tasks, not 48 independent tasks. '
        'No human equivalence review has been completed.\n')
    print(detail)


if __name__ == '__main__':
    main()
