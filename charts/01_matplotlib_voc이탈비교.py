import csv
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "charts" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def select_font():
    preferred = ["Malgun Gothic", "NanumGothic", "AppleGothic", "Microsoft YaHei", "Arial Unicode MS"]
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in preferred:
        if name in available:
            return name
    return None


def read_csv_rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def calculate_rates():
    customers = read_csv_rows(DATA_DIR / "data_customers.csv")
    vocs = read_csv_rows(DATA_DIR / "data_voc.csv")

    customer_map = {row["customer_id"]: row for row in customers}

    total_customers = len(customers)
    churned_customers = sum(1 for row in customers if row.get("churn_yn") == "Y")
    overall_rate = (churned_customers / total_customers * 100) if total_customers else 0.0

    target_ids = {
        row["customer_id"]
        for row in vocs
        if row.get("category") == "해지관련" and row.get("sentiment") == "부정"
    }
    target_customers = [customer_map[cid] for cid in target_ids if cid in customer_map]
    target_churned = sum(1 for row in target_customers if row.get("churn_yn") == "Y")
    target_rate = (target_churned / len(target_customers) * 100) if target_customers else 0.0

    return overall_rate, target_rate, target_ids


def plot_comparison(overall_rate, target_rate):
    font_name = select_font()
    if font_name:
        plt.rcParams["font.family"] = font_name
    else:
        plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["axes.unicode_minus"] = False

    labels = ["전체 고객", "해지관련 부정 VOC 이력 있음"]
    values = [overall_rate, target_rate]
    colors = ["#4C78A8", "#E45756"]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, values, color=colors, width=0.6)

    ax.set_title("고객 이탈율 비교", fontsize=14, pad=10)
    ax.set_ylabel("이탈율 (%)")
    ax.set_ylim(0, max(values) * 1.25 + 5)
    ax.grid(axis="y", linestyle="--", alpha=0.3)

    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.5,
            f"{value:.1f}%",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
        )

    plt.tight_layout()
    output_path = OUTPUT_DIR / "01_matplotlib_voc이탈비교.png"
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return output_path


if __name__ == "__main__":
    overall_rate, target_rate, target_ids = calculate_rates()
    output_path = plot_comparison(overall_rate, target_rate)
    print(f"전체 고객 이탈율: {overall_rate:.1f}%")
    print(f"해지관련 부정 VOC 이력 있음 고객 이탈율: {target_rate:.1f}%")
    print(f"저장 완료: {output_path}")
