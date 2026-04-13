from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


OUT_DIR = Path(__file__).resolve().parent


BOARD_DATA = [
    {
        "label": "Baseline\nnoop",
        "mechanic": "noop_mechanic_file",
        "balance_gap": 0.000,
        "depth": 0.667,
        "aggregate": 0.834,
    },
    {
        "label": "Run 1\nline_lock",
        "mechanic": "line_lock_on_placement",
        "balance_gap": 0.333,
        "depth": 1.000,
        "aggregate": 0.834,
    },
    {
        "label": "Run 2\nsplash_freeze",
        "mechanic": "placement_with_splash_freeze_line",
        "balance_gap": 0.000,
        "depth": 0.667,
        "aggregate": 0.834,
    },
    {
        "label": "Run 3\nsight_block",
        "mechanic": "line_of_sight_block_on_placement",
        "balance_gap": 0.000,
        "depth": 0.667,
        "aggregate": 0.834,
    },
]


CARD_DATA = [
    {
        "label": "Baseline\nnoop",
        "mechanic": "noop_card_mechanic",
        "balance_gap": 0.500,
        "depth": -0.083,
        "aggregate": 0.250,
    },
    {
        "label": "Sym Init\nlockout",
        "mechanic": "last_card_lockout",
        "balance_gap": 0.333,
        "depth": 0.167,
        "aggregate": 0.417,
    },
    {
        "label": "Sym Rev\ncombo",
        "mechanic": "echo_combo_rule",
        "balance_gap": 0.417,
        "depth": 0.250,
        "aggregate": 0.416,
    },
    {
        "label": "Bias Init\ndouble_play",
        "mechanic": "temporary_double_play_buff",
        "balance_gap": 0.167,
        "depth": 0.000,
        "aggregate": 0.416,
    },
    {
        "label": "Bias Rev\nparity_shield",
        "mechanic": "one_turn_parity_shield_after_odd_play",
        "balance_gap": 0.667,
        "depth": 0.500,
        "aggregate": 0.416,
    },
    {
        "label": "Strat Init\nbluff",
        "mechanic": "last_card_bonus_bluff",
        "balance_gap": 0.250,
        "depth": 0.250,
        "aggregate": 0.500,
    },
    {
        "label": "Strat Rev\nlucky_flip",
        "mechanic": "hand_size_parity_lucky_flip",
        "balance_gap": 0.833,
        "depth": -0.167,
        "aggregate": 0.084,
    },
]


def _base_style():
    plt.rcParams.update(
        {
            "font.size": 12,
            "axes.titlesize": 22,
            "axes.labelsize": 14,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "figure.facecolor": "#fffaf4",
            "axes.facecolor": "#fffaf4",
            "axes.edgecolor": "#3a3a3a",
            "axes.titleweight": "bold",
            "axes.labelcolor": "#2c2c2c",
            "text.color": "#2c2c2c",
        }
    )


def _annotate_bars(ax, bars, fmt="{:.3f}", dy=0.02):
    for bar in bars:
        value = bar.get_height()
        xpos = bar.get_x() + bar.get_width() / 2
        if value >= 0:
            ypos = value + dy
            va = "bottom"
        else:
            ypos = value - dy
            va = "top"
        ax.text(xpos, ypos, fmt.format(value), ha="center", va=va, fontsize=10)


def make_board_chart():
    _base_style()
    labels = [item["label"] for item in BOARD_DATA]
    balance = [item["balance_gap"] for item in BOARD_DATA]
    depth = [item["depth"] for item in BOARD_DATA]
    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(14, 8), dpi=160)
    bars1 = ax.bar(x - width / 2, balance, width, label="Balance Gap", color="#d95f02")
    bars2 = ax.bar(x + width / 2, depth, width, label="Depth", color="#1b9e77")

    ax.set_title("Board Experiment: Balance vs Strategic Depth")
    ax.set_ylabel("Metric Value")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.15)
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.legend(frameon=False, ncol=2, loc="upper left")
    _annotate_bars(ax, bars1)
    _annotate_bars(ax, bars2)

    fig.tight_layout()
    fig.savefig(OUT_DIR / "slide1_board_balance_depth.png", bbox_inches="tight")
    plt.close(fig)


def make_card_chart():
    _base_style()
    labels = [item["label"] for item in CARD_DATA]
    balance = [item["balance_gap"] for item in CARD_DATA]
    depth = [item["depth"] for item in CARD_DATA]
    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(16, 8), dpi=160)
    bars1 = ax.bar(x - width / 2, balance, width, label="Balance Gap", color="#e76f51")
    bars2 = ax.bar(x + width / 2, depth, width, label="Depth", color="#2a9d8f")

    ax.set_title("Card Experiment: Balance vs Strategic Depth")
    ax.set_ylabel("Metric Value")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylim(-0.25, 0.95)
    ax.axhline(0, color="#5c5c5c", linewidth=1)
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.legend(frameon=False, ncol=2, loc="upper left")
    _annotate_bars(ax, bars1)
    _annotate_bars(ax, bars2)

    fig.tight_layout()
    fig.savefig(OUT_DIR / "slide2_card_balance_depth.png", bbox_inches="tight")
    plt.close(fig)


def make_comparison_chart():
    _base_style()
    fig, ax = plt.subplots(figsize=(14, 8), dpi=160)

    board_x = [item["balance_gap"] for item in BOARD_DATA]
    board_y = [item["depth"] for item in BOARD_DATA]
    card_x = [item["balance_gap"] for item in CARD_DATA]
    card_y = [item["depth"] for item in CARD_DATA]

    ax.scatter(board_x, board_y, s=180, c="#1f77b4", label="Board Mechanics", alpha=0.9)
    ax.scatter(card_x, card_y, s=180, c="#c44536", label="Card Mechanics", alpha=0.85, marker="s")

    board_label_style = {
        "noop_mechanic_file": {"text": "board baseline", "xytext": (10, 12)},
        "placement_with_splash_freeze_line": {"text": "splash freeze", "xytext": (10, 28)},
        "line_of_sight_block_on_placement": {"text": "line-of-sight block", "xytext": (10, 44)},
        "line_lock_on_placement": {"text": "line lock", "xytext": (8, 8)},
    }
    for item in BOARD_DATA:
        style = board_label_style[item["mechanic"]]
        ax.annotate(
            style["text"],
            (item["balance_gap"], item["depth"]),
            textcoords="offset points",
            xytext=style["xytext"],
            fontsize=9,
        )
    for item in CARD_DATA:
        ax.annotate(
            item["mechanic"].replace("_", "\n", 1),
            (item["balance_gap"], item["depth"]),
            textcoords="offset points",
            xytext=(8, -14),
            fontsize=8,
        )

    ax.axvline(0.2, color="#6c757d", linestyle="--", linewidth=1, alpha=0.8)
    ax.axhline(0.2, color="#6c757d", linestyle="--", linewidth=1, alpha=0.8)
    ax.text(0.02, 0.92, "Ideal region:\nlow balance gap,\nhigh depth", fontsize=11, transform=ax.transAxes)

    ax.set_title("Board vs Card: Evaluation Landscape")
    ax.set_xlabel("Balance Gap (lower is better)")
    ax.set_ylabel("Depth (higher is better)")
    ax.set_xlim(-0.02, 0.9)
    ax.set_ylim(-0.25, 1.1)
    ax.grid(True, linestyle="--", alpha=0.25)
    ax.legend(frameon=False, loc="lower left")

    fig.tight_layout()
    fig.savefig(OUT_DIR / "slide3_board_vs_card_scatter.png", bbox_inches="tight")
    plt.close(fig)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    make_board_chart()
    make_card_chart()
    make_comparison_chart()
    print(f"Generated charts in {OUT_DIR}")


if __name__ == "__main__":
    main()
