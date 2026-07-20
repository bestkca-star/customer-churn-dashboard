import csv
from pathlib import Path

import plotly.express as px


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def read_csv_rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def calculate_recontact_buckets():
    consultations = read_csv_rows(DATA_DIR / "data_consultations.csv")
    customers = read_csv_rows(DATA_DIR / "data_customers.csv")

    customer_map = {row["customer_id"]: row for row in customers}

    customer_recontact_counts = {}
    for row in consultations:
        if row.get("is_recontact") == "Y":
            customer_id = row["customer_id"]
            customer_recontact_counts[customer_id] = customer_recontact_counts.get(customer_id, 0) + 1

    bucket_labels = ["0회", "1회", "2회 이상"]
    bucket_results = []

    for label in bucket_labels:
        bucket_results.append({"구간": label, "고객수": 0, "이탈고객수": 0})

    for customer_id, customer in customer_map.items():
        recontact_count = customer_recontact_counts.get(customer_id, 0)
        if recontact_count >= 2:
            bucket = "2회 이상"
        elif recontact_count == 1:
            bucket = "1회"
        else:
            bucket = "0회"

        for item in bucket_results:
            if item["구간"] == bucket:
                item["고객수"] += 1
                if customer.get("churn_yn") == "Y":
                    item["이탈고객수"] += 1
                break

    for item in bucket_results:
        item["이탈율"] = round((item["이탈고객수"] / item["고객수"] * 100) if item["고객수"] else 0.0, 2)

    total_customers = len(customers)
    total_churned = sum(1 for row in customers if row.get("churn_yn") == "Y")
    overall_rate = round((total_churned / total_customers * 100) if total_customers else 0.0, 2)

    return bucket_results, overall_rate


if __name__ == "__main__":
    bucket_results, overall_rate = calculate_recontact_buckets()

    df = []
    for item in bucket_results:
        df.append({
            "구간": item["구간"],
            "이탈율": item["이탈율"],
            "고객수": item["고객수"],
            "이탈고객수": item["이탈고객수"],
        })

    fig = px.bar(
        df,
        x="구간",
        y="이탈율",
        color="구간",
        color_discrete_map={
            "0회": "#4C78A8",
            "1회": "#F58518",
            "2회 이상": "#E45756",
        },
        text=[f"{row['이탈율']:.1f}%" for row in df],
        labels={"구간": "재문의 횟수 구간", "이탈율": "이탈율 (%)"},
        title="재문의 횟수 구간별 이탈율",
        hover_data={"고객수": True, "이탈고객수": True, "이탈율": ":.2f"},
    )

    fig.add_hline(
        y=overall_rate,
        line_dash="dash",
        line_color="#2F4F4F",
        line_width=2,
        annotation_text=f"전체 평균 이탈율 {overall_rate:.1f}%",
        annotation_position="top left",
    )

    fig.update_traces(textposition="outside", marker_line_width=0)
    fig.update_layout(
        template="plotly_white",
        yaxis_title="이탈율 (%)",
        xaxis_title="재문의 횟수 구간",
        yaxis_range=[0, max([row["이탈율"] for row in df]) * 1.25 + 5],
        font=dict(family="Malgun Gothic, Arial, sans-serif"),
    )

    fig.show()
