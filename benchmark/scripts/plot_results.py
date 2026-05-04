#!/usr/bin/env python3
"""
Generates benchmark charts from eval result files.
Produces two separate high-res images:
  • yolo_bench_overall.png   — Exact %, Norm %, Token F1 per model
  • yolo_bench_categories.png — per-category breakdown

Usage:
    python3 plot_results.py results/*.json
    python3 plot_results.py results/*.json --out-dir results/
"""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np


CATEGORY_LABELS = {
    "python":     "Python",
    "typescript": "TypeScript",
    "git":        "Git",
    "shell":      "Shell",
    "docker":     "Docker",
    "npm":        "npm",
    "pip":        "pip",
    "nodejs":     "Node.js",
    "cargo":      "Cargo/Rust",
    "venv":       "venv/conda",
    "database":   "Database",
    "ssh":        "SSH",
    "cloud":      "Cloud",
    "make":       "Make",
    "yarn":       "Yarn",
}

# Preferred order: Python, TypeScript first, then by n size descending
CATEGORY_ORDER = [
    "python",       # n=41
    "typescript",   # n=12  (pinned 2nd)
    "git",          # n=25
    "shell",        # n=20
    "docker",       # n=19
    "npm",          # n=15
    "pip",          # n=15
    "nodejs",       # n=14
    "cargo",        # n=13
    "venv",         # n=10
    "database",     # n=10
    "ssh",          # n=9
    "cloud",        # n=6
    "make",         # n=5
    "yarn",         # n=4
]

MODEL_COLORS = [
    "#50DC78",  # green   — YOLO-7B v2
    "#7C6AF5",  # purple  — YOLO-7B v1
    "#4A9EDB",  # blue    — base 7B
    "#F5A623",  # orange  — YOLO-1.5B
]

MODEL_SHORT = {
    "yolov2":           "YOLO-7B v2",
    "yolo-7b":          "YOLO-7B v1",
    "qwen2.5-coder:7b": "Qwen2.5-7B (base)",
    "yolo-coder":       "YOLO-1.5B",
}

BG_DARK  = "#0D0D12"
BG_PANEL = "#13131A"
GRID_COL = "#1E1E2E"
SPINE_COL = "#2A2A3C"
LABEL_COL = "#AAAACC"
TITLE_COL = "#EEEEFF"
VALUE_COL = "#E0E0FF"


def load_result(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def short_name(model: str) -> str:
    return MODEL_SHORT.get(model, model)


def style_ax(ax):
    ax.set_facecolor(BG_PANEL)
    ax.tick_params(colors=LABEL_COL, labelsize=9)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color(SPINE_COL)
    ax.spines["bottom"].set_color(SPINE_COL)
    ax.grid(axis="y", color=GRID_COL, linewidth=0.7, zorder=0)


def make_legend(fig, models, colors, n_models, y=-0.04):
    patches = [
        mpatches.Patch(color=colors[mi], label=short_name(m["meta"]["model"]))
        for mi, m in enumerate(models)
    ]
    fig.legend(handles=patches, loc="lower center", ncol=n_models,
               frameon=False, fontsize=11, labelcolor=LABEL_COL,
               bbox_to_anchor=(0.5, y))


# ── Chart 1: Overall ──────────────────────────────────────────────────────────

def plot_overall(models, colors, out_path: Path):
    n_models = len(models)
    metric_labels = ["Exact %", "Normalized %", "Token F1 ×100"]
    x_pos = np.arange(len(metric_labels))
    bar_w = 0.22
    offsets = np.linspace(-(n_models - 1) / 2, (n_models - 1) / 2, n_models) * bar_w

    fig, ax = plt.subplots(figsize=(9, 6))
    fig.patch.set_facecolor(BG_DARK)
    style_ax(ax)

    for mi, (data, color) in enumerate(zip(models, colors)):
        s = data["summary"]
        values = [s["exact_match_pct"], s["normalized_match_pct"], s["avg_token_f1"] * 100]
        xs = x_pos + offsets[mi]
        bars = ax.bar(xs, values, width=bar_w * 0.85, color=color,
                      zorder=3, alpha=0.93)
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.7,
                    f"{val:.1f}",
                    ha="center", va="bottom",
                    fontsize=9.5, color=VALUE_COL, fontweight="bold")

    ax.set_xticks(x_pos)
    ax.set_xticklabels(metric_labels, fontsize=11, color=TITLE_COL)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Score (%)", color=LABEL_COL, fontsize=10)
    ax.yaxis.set_tick_params(labelcolor=LABEL_COL)
    ax.set_xlim(-0.5, len(metric_labels) - 0.5)

    fig.suptitle("YOLO-Bench  ·  Overall Results", color="#FFFFFF",
                 fontsize=15, fontweight="bold", y=0.97)

    make_legend(fig, models, colors, n_models, y=-0.06)
    plt.tight_layout(rect=[0, 0.08, 1, 0.95])
    plt.savefig(out_path, dpi=240, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"Overall chart  → {out_path.resolve()}")


# ── Chart 2: Category breakdown ───────────────────────────────────────────────

def plot_categories(models, colors, out_path: Path):
    n_models = len(models)
    categories = CATEGORY_ORDER
    n_cats = len(categories)

    bar_w = 0.22
    offsets = np.linspace(-(n_models - 1) / 2, (n_models - 1) / 2, n_models) * bar_w

    # 5 cols × 3 rows grid
    n_cols = 5
    n_rows = int(np.ceil(n_cats / n_cols))
    fig, axes = plt.subplots(n_rows, n_cols,
                             figsize=(n_cols * 3.6, n_rows * 4.0))
    fig.patch.set_facecolor(BG_DARK)
    axes_flat = axes.flatten()

    for ci, cat in enumerate(categories):
        ax = axes_flat[ci]
        style_ax(ax)
        label = CATEGORY_LABELS.get(cat, cat)

        n_ex = 0
        for mi, (data, color) in enumerate(zip(models, colors)):
            by_cat = data["summary"].get("by_category", {})
            entry = by_cat.get(cat, {})
            val = entry.get("exact_match", 0.0)
            if n_ex == 0:
                n_ex = entry.get("count", 0)
            offset = offsets[mi]
            ax.bar(offset, val, width=bar_w * 0.85, color=color,
                   zorder=3, alpha=0.93)
            if val > 0:
                ax.text(offset, val + 1.5, f"{val:.0f}",
                        ha="center", va="bottom",
                        fontsize=9, color=VALUE_COL, fontweight="bold")

        ax.set_title(f"{label}  (n={n_ex})", color=TITLE_COL,
                     fontsize=10.5, fontweight="bold", pad=7)
        ax.set_ylim(0, 105)
        ax.set_xticks([])
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.set_yticklabels(["0", "25", "50", "75", "100"],
                           fontsize=8, color=LABEL_COL)
        ax.set_xlim(-0.5, 0.5)

    # Hide unused axes
    for ci in range(n_cats, len(axes_flat)):
        axes_flat[ci].set_visible(False)

    fig.suptitle("YOLO-Bench  ·  Results by Category  (Exact Match %)",
                 color="#FFFFFF", fontsize=14, fontweight="bold", y=1.01)

    make_legend(fig, models, colors, n_models, y=-0.04)
    plt.tight_layout(rect=[0, 0.05, 1, 1])
    plt.savefig(out_path, dpi=240, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"Category chart → {out_path.resolve()}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", help="Result JSON files to compare")
    parser.add_argument("--out-dir", default=None,
                        help="Directory to save charts (defaults to same dir as first file)")
    args = parser.parse_args()

    models = [load_result(p) for p in args.files]
    models.sort(key=lambda d: d["summary"]["normalized_match_pct"], reverse=True)

    n_models = len(models)
    colors = MODEL_COLORS[:n_models]

    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        out_dir = Path(args.files[0]).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    plot_overall(models, colors, out_dir / "yolo_bench_overall.png")
    plot_categories(models, colors, out_dir / "yolo_bench_categories.png")


if __name__ == "__main__":
    main()
