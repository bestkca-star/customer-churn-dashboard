import csv
from pathlib import Path

import plotly.express as px


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def read_csv_rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def calculate_region_metrics():
    customers = read_csv_rows(DATA_DIR / "data_customers.csv")
    region_stats = {}

    for row in customers:
        region = row.get("region", "")
        stats = region_stats.setdefault(region, {"customer_count": 0, "churn_count": 0})
        stats["customer_count"] += 1
        if row.get("churn_yn") == "Y":
            stats["churn_count"] += 1

    result = []
    for region, stats in region_stats.items():
        result.append({
            "region": region,
            "customer_count": stats["customer_count"],
            "churn_count": stats["churn_count"],
            "churn_rate": round(stats["churn_count"] / stats["customer_count"] * 100, 2),
        })

    result.sort(key=lambda x: x["churn_rate"], reverse=True)
    return result


if __name__ == "__main__":
    data = calculate_region_metrics()

    fig = px.bar(
        data,
        x="region",
        y="churn_rate",
        color="region",
        text=[f"{row['churn_rate']:.1f}%" for row in data],
        labels={"region": "지역", "churn_rate": "이탈율 (%)"},
        title="지역별 이탈율",
        hover_data={"customer_count": True, "churn_count": True, "churn_rate": ":.2f"},
        color_discrete_map={
            "부산": "#E45756",
            "대구": "#E45756",
            "인천": "#4C78A8",
            "서울": "#4C78A8",
            "경기": "#4C78A8",
            "기타": "#4C78A8",
        },
    )

    fig.update_traces(textposition="outside", marker_line_width=0)
    fig.update_layout(
        template="plotly_white",
        yaxis_title="이탈율 (%)",
        xaxis_title="지역",
        yaxis_range=[0, max(row["churn_rate"] for row in data) * 1.25 + 5],
        font=dict(family="Malgun Gothic, Arial, sans-serif"),
        annotations=[
            dict(
                text="인천은 표본이 53건이지만 이탈 1건뿐이라는 점을 참고하세요.",
                x=0.5,
                y=-0.22,
                xref="paper",
                yref="paper",
                showarrow=False,
                align="center",
                font=dict(size=12)
            )
        ],
    )

    fig.show()
