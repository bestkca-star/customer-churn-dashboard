import csv
from pathlib import Path

import plotly.express as px


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def read_csv_rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def calculate_plan_metrics():
    customers = read_csv_rows(DATA_DIR / "data_customers.csv")
    plan_stats = {}

    for row in customers:
        plan = row.get("plan", "")
        stats = plan_stats.setdefault(plan, {"customer_count": 0, "churn_count": 0})
        stats["customer_count"] += 1
        if row.get("churn_yn") == "Y":
            stats["churn_count"] += 1

    result = []
    for plan, stats in plan_stats.items():
        result.append({
            "plan": plan,
            "customer_count": stats["customer_count"],
            "churn_count": stats["churn_count"],
            "churn_rate": round(stats["churn_count"] / stats["customer_count"] * 100, 2),
        })

    result.sort(key=lambda x: x["churn_rate"], reverse=True)
    return result


if __name__ == "__main__":
    data = calculate_plan_metrics()

    fig = px.bar(
        data,
        x="plan",
        y="churn_rate",
        color="plan",
        text=[f"{row['churn_rate']:.1f}%" for row in data],
        labels={"plan": "요금제", "churn_rate": "이탈율 (%)"},
        title="요금제별 이탈율",
        hover_data={"customer_count": True, "churn_count": True, "churn_rate": ":.2f"},
        color_discrete_map={
            "베이직": "#E45756",
            "스탠다드": "#4C78A8",
            "프리미엄": "#F58518",
        },
    )

    fig.update_traces(textposition="outside", marker_line_width=0)
    fig.update_layout(
        template="plotly_white",
        yaxis_title="이탈율 (%)",
        xaxis_title="요금제",
        yaxis_range=[0, max(row["churn_rate"] for row in data) * 1.25 + 5],
        font=dict(family="Malgun Gothic, Arial, sans-serif"),
    )

    fig.show()
