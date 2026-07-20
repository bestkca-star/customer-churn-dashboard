import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import plotly.express as px


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def read_csv_rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def calculate_tenure_and_avg_data():
    customers = read_csv_rows(DATA_DIR / "data_customers.csv")
    usage_rows = read_csv_rows(DATA_DIR / "data_usage_history.csv")

    usage_by_customer = defaultdict(list)
    for row in usage_rows:
        usage_by_customer[row["customer_id"]].append(float(row["data_gb"]))

    results = []
    for customer in customers:
        customer_id = customer["customer_id"]
        join_date = customer.get("join_date")
        churn_yn = customer.get("churn_yn")

        if join_date:
            join_dt = datetime.strptime(join_date, "%Y-%m-%d")
            end_dt = datetime.strptime("2024-12-31", "%Y-%m-%d")
            months = (end_dt.year - join_dt.year) * 12 + (end_dt.month - join_dt.month)
        else:
            months = None

        data_values = usage_by_customer.get(customer_id, [])
        avg_data_gb = round(sum(data_values) / len(data_values), 2) if data_values else None

        results.append({
            "customer_id": customer_id,
            "tenure_months": months,
            "avg_data_gb": avg_data_gb,
            "churn_yn": churn_yn,
        })

    return results


if __name__ == "__main__":
    data = calculate_tenure_and_avg_data()

    fig = px.scatter(
        data,
        x="tenure_months",
        y="avg_data_gb",
        color="churn_yn",
        color_discrete_map={"Y": "#E45756", "N": "#4C78A8"},
        hover_data={
            "customer_id": True,
            "tenure_months": True,
            "avg_data_gb": True,
            "churn_yn": True,
        },
        labels={
            "tenure_months": "가입기간(개월)",
            "avg_data_gb": "평균 데이터 사용량(GB)",
            "churn_yn": "이탈 여부",
        },
        title="가입기간과 평균 데이터 사용량 산점도",
    )

    fig.update_layout(
        template="plotly_white",
        font=dict(family="Malgun Gothic, Arial, sans-serif"),
    )

    fig.show()
