#!/usr/bin/env python3
"""Export observed multi-model errors, replication detail and complete CSV tables."""
import argparse
import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".mplconfig"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":12, "pdf.fonttype":42, "svg.fonttype":"none"})
LANGUAGES = ["en", "es", "pt"]
COLORS = ["#334155", "#087e8b", "#d79131"]


def save(fig, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    for extension in ["png", "pdf", "svg"]:
        fig.savefig(output.parent / (output.name + "." + extension), dpi=200, facecolor="white")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=ROOT / "analysis/local-comparison-v1.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "figures")
    args = parser.parse_args()
    data = json.loads(args.summary.read_text())
    models = data["models"]
    if not models or not data["complete"] or any(m["valid"] != m["planned"] for m in models):
        raise ValueError("Figures require all planned models and all judgments; do not plot partial results")
    for model in models:
        for rate in model["rates"]:
            if rate["valid"] != rate["planned"]:
                raise ValueError("Incomplete language group")
    labels = [m["model"] for m in models]
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 5.6))
    y = np.arange(len(models))
    for ax, key, title, numerator, denominator in [
        (axes[0], "false_accept_rate", "Incorrect values accepted", "false_accepts", "negative_valid"),
        (axes[1], "false_reject_rate", "Acceptable values rejected", "false_rejects", "positive_valid")]:
        for j, language in enumerate(LANGUAGES):
            rates = [next(r for r in m["rates"] if r["experiment"] == "numeric_probe" and r["language"] == language) for m in models]
            positions = y + (j-1)*0.23
            ax.barh(positions, [100*r[key] for r in rates], height=0.20,
                    color=COLORS[j], label=language.upper())
            for pos, r in zip(positions, rates):
                ax.text(min(100*r[key]+1.2, 102), pos, f"{r[numerator]}/{r[denominator]}",
                        va="center", fontsize=11, color="#253347")
        ax.set(yticks=y, yticklabels=labels, xlim=(0, 115), xticks=[0,25,50,75,100],
               xlabel="Error rate (%)", title=title)
        ax.invert_yaxis()
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_axisbelow(True)
        ax.grid(axis="x", alpha=0.15)
    axes[0].legend(loc="lower right", frameon=False)
    fig.suptitle("Do small local judges apply APEX's numeric rules?", fontsize=17, fontweight="bold", color="#253347", y=.97)
    fig.text(.5,.88,"6 criteria from 3 selected tasks · identical numbers across languages · 3 repeats",ha="center",fontsize=11)
    fig.subplots_adjust(top=.79, bottom=.23, left=.15, right=.97, wspace=.70)
    fig.text(.03,.12,"648 numeric judgments · lower is better · counts show errors / applicable judgments",fontsize=10)
    fig.text(.03,.075,"References: published numeric bounds. Language review pending; EN/ES primary, PT exploratory.",fontsize=10,color="#52677e")
    fig.text(.03,.035,"Three selected tasks; repeated calls are not independent tasks. Not the APEX leaderboard.",fontsize=10,color="#52677e")
    save(fig, args.output_dir / "local_model_comparison")
    targets = [("1172-complete",5,"Risk present\nexpected: pass"),
               ("1172-wrong_sam",4,"Wrong SAM\nexpected: fail"),
               ("1172-complete",2,"Correct count\nexpected: pass")]
    values = []
    counts = []
    for model in models:
        lookup = {(c["pair_id"],c["criterion_id"],c["language"]):c for c in model["cells"]}
        selected = [lookup[(pair,cid,lang)] for pair,cid,_ in targets for lang in ["en","es"]]
        values.append([c["pass_fraction"] for c in selected])
        counts.append([f"{c['passes']}/{c['valid']}" for c in selected])
    fig, ax = plt.subplots(figsize=(10, 4.9))
    grid = ax.imshow(values, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    ax.set(yticks=range(len(labels)),yticklabels=labels,xticks=range(6),xticklabels=["EN","ES"]*3)
    for i,row in enumerate(values):
        for j,v in enumerate(row):
            ax.text(j,i,counts[i][j],ha="center",va="center",fontweight="bold",fontsize=13,
                    color="white" if v>.6 else "#253347")
    for x in [1.5,3.5]: ax.axvline(x,color="white",lw=5)
    for i,(_,_,label) in enumerate(targets):
        ax.text((2*i+.5+.5)/6,1.04,label,transform=ax.transAxes,ha="center",fontsize=11)
    fig.colorbar(grid,ax=ax,fraction=.03,pad=.03,label="Approval fraction")
    fig.suptitle("Do the original pilot failures persist across judges?",fontsize=16,fontweight="bold",y=.98)
    fig.subplots_adjust(top=.72,bottom=.25,left=.18,right=.91)
    fig.text(.025,.12,"Fresh replication of three checks identified before this expansion · all planned cells exported separately",fontsize=9)
    fig.text(.025,.065,"Constructed responses, one task (1172); design labels and intended EN/ES equivalence await expert review.",fontsize=9,color="#52677e")
    save(fig,args.output_dir / "local_replication_detail")
    for name in ["cells", "contrasts", "rates"]:
        rows = [dict(model=m["model"],**r) for m in models for r in m[name]]
        with (args.summary.parent / f"local-comparison-v1-{name}.csv").open("w",newline="") as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
            writer.writeheader();writer.writerows(rows)
    (args.output_dir / "local_model_comparison.md").write_text(
        "# Numeric-rule adherence in the local comparison\n\n"
        "Observed results from four local models: six numeric criteria from three selected APEX tasks, "
        "three values per criterion, three response languages and three repeats (648 calls). "
        "Left: approvals of out-of-range values (21 judgments per model/language). "
        "Right: rejections of acceptable values (33 judgments per model/language). "
        "Counts are repeated judgments, not independent tasks. English rubric/instructions; "
        "EN/ES is primary and PT secondary. Numeric references follow published rubric predicates; "
        "independent language review is pending. No population inference or leaderboard claim. "
        "The separate full-response replication contributes another 432 calls.\n")
    print(f"Exported two figures and complete CSV tables to {args.output_dir}")


if __name__ == "__main__":
    main()
