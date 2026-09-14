#!/usr/bin/env python3
"""Compact figure for the one-page proposal: equal accuracy hides opposite
error profiles (local-comparison-v1) and stability does not imply
correctness (content-paraphrase-v1). Reads the frozen analysis CSV/JSON."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, MUTED = "#0b0b0b", "#52514e"
ORDER = ["qwen3:1.7b", "qwen3:4b", "qwen3:8b", "gemma3:4b"]


def load_rates():
    rows = list(csv.DictReader(open(ROOT / "analysis/local-comparison-v1-rates.csv")))
    cols = rows[0].keys()
    def pick(*cands):
        for c in cands:
            if c in cols:
                return c
        raise KeyError(cands)
    m = pick("model"); lang = pick("language", "lang")
    fa_n = pick("false_accepts"); fa_d = pick("negative_valid")
    fr_n = pick("false_rejects"); fr_d = pick("positive_valid")
    out = {}
    for r in rows:
        if r[lang].lower() == "en" and r["experiment"] == "numeric_probe":
            out[r[m]] = (int(r[fa_n]), int(r[fa_d]), int(r[fr_n]), int(r[fr_d]))
    return out


def single_panel(rates):
    """Left panel alone, sized for a half-width column in the one-pager."""
    fig, ax = plt.subplots(figsize=(4.6, 3.3))
    fig.patch.set_facecolor("white")
    y = list(range(len(ORDER)))[::-1]
    h = 0.34
    for yi, model in zip(y, ORDER):
        fa_n, fa_d, fr_n, fr_d = rates[model]
        ax.barh(yi + h / 2, 100 * fa_n / fa_d, h, color=BLUE, edgecolor="white", linewidth=1)
        ax.barh(yi - h / 2, 100 * fr_n / fr_d, h, color=ORANGE, edgecolor="white", linewidth=1)
        ax.text(100 * fa_n / fa_d + 1.5, yi + h / 2, f"{fa_n}/{fa_d}", va="center", fontsize=9.5, color=INK)
        ax.text(100 * fr_n / fr_d + 1.5, yi - h / 2, f"{fr_n}/{fr_d}", va="center", fontsize=9.5, color=INK)
        ax.text(-2, yi, f"{model}\n12/54 errors", ha="right", va="center", fontsize=9.5, color=INK)
    ax.set_yticks([]); ax.set_xlim(0, 78)
    ax.set_xlabel("Error rate, English numeric checks (%)", fontsize=9.5, color=MUTED)
    ax.set_title("Same total error, opposite error profiles", fontsize=11.5, loc="left", color=INK, pad=8)
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=BLUE), plt.Rectangle((0, 0), 1, 1, color=ORANGE)],
              labels=["incorrect value approved", "acceptable value rejected"], frameon=False, fontsize=9,
              loc="upper center", bbox_to_anchor=(0.42, -0.2), ncol=1)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color("#d0cfcb"); ax.spines["bottom"].set_color("#d0cfcb")
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="x", color="#eceae5", linewidth=0.8); ax.set_axisbelow(True)
    fig.tight_layout()
    for ext in ("png", "pdf", "svg"):
        fig.savefig(str(ROOT / "figures" / f"acceptance_single.{ext}"), dpi=220, bbox_inches="tight", facecolor="white")



def main():
    single_panel(load_rates())
    print("Saved figures/acceptance_single.{png,pdf,svg}")


if __name__ == "__main__":
    main()
