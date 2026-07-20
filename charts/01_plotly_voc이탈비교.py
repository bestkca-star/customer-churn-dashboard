import csv
import webbrowser
from pathlib import Path

import plotly.express as px


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "charts" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


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

    return overall_rate, target_rate, len(customers), len(target_customers), churned_customers, target_churned


if __name__ == "__main__":
    overall_rate, target_rate, total_customers, target_customer_count, churned_customers, target_churned = calculate_rates()

    labels = ["전체 고객", "해지관련 부정 VOC 이력 있음"]
    values = [overall_rate, target_rate]
    counts = [total_customers, target_customer_count]
    churn_counts = [churned_customers, target_churned]

    df = {
        "구분": labels,
        "이탈율": values,
        "고객수": counts,
        "이탈고객수": churn_counts,
    }

    fig = px.bar(
        df,
        x="구분",
        y="이탈율",
        color="구분",
        color_discrete_map={
            "전체 고객": "#4C78A8",
            "해지관련 부정 VOC 이력 있음": "#E45756",
        },
        text=[f"{v:.1f}%" for v in values],
        labels={"구분": "그룹", "이탈율": "이탈율 (%)"},
        hover_data={"고객수": True, "이탈고객수": True, "이탈율": ":.1f"},
        title="고객 이탈율 비교"
    )

    fig.update_traces(textposition="outside", hovertemplate="<b>%{x}</b><br>고객 수: %{customdata[0]}명<br>이탈 고객 수: %{customdata[1]}명<br>이탈율: %{y:.1f}%<extra></extra>")
    fig.update_layout(
        xaxis_title="구분",
        yaxis_title="이탈율 (%)",
        yaxis_range=[0, max(values) * 1.25 + 5],
        template="plotly_white",
        font=dict(family="Malgun Gothic, Arial, sans-serif"),
    )

    fig.update_traces(customdata=list(zip(counts, churn_counts)))

    output_html = OUTPUT_DIR / "01_plotly_voc이탈비교.html"
    fig.write_html(output_html, include_plotlyjs="inline")
    print(f"저장 완료: {output_html}")

    try:
        webbrowser.open(output_html.resolve().as_uri())
        print("브라우저에서 열었습니다.")
    except Exception as e:
        print(f"브라우저 열기 실패: {e}")

    fig.show()
