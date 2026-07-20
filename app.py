import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def read_csv_rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_data():
    customers = read_csv_rows(DATA_DIR / "data_customers.csv")
    vocs = read_csv_rows(DATA_DIR / "data_voc.csv")
    consultations = read_csv_rows(DATA_DIR / "data_consultations.csv")
    satisfactions = read_csv_rows(DATA_DIR / "data_satisfaction.csv")
    usage_rows = read_csv_rows(DATA_DIR / "data_usage_history.csv")
    return customers, vocs, consultations, satisfactions, usage_rows


def build_overall_metrics(customers):
    total_customers = len(customers)
    churned_customers = sum(1 for row in customers if row.get("churn_yn") == "Y")
    overall_rate = round((churned_customers / total_customers * 100) if total_customers else 0.0, 1)
    return total_customers, churned_customers, overall_rate


def build_voc_chart(customers, vocs):
    customer_map = {row["customer_id"]: row for row in customers}
    total_customers = len(customers)
    churned_customers = sum(1 for row in customers if row.get("churn_yn") == "Y")
    overall_rate = round((churned_customers / total_customers * 100) if total_customers else 0.0, 1)

    target_ids = {
        row["customer_id"]
        for row in vocs
        if row.get("category") == "해지관련" and row.get("sentiment") == "부정"
    }
    target_customers = [customer_map[cid] for cid in target_ids if cid in customer_map]
    target_churned = sum(1 for row in target_customers if row.get("churn_yn") == "Y")
    target_rate = round((target_churned / len(target_customers) * 100) if target_customers else 0.0, 1)

    labels = ["전체 고객", "해지관련 부정 VOC 이력 있음"]
    values = [overall_rate, target_rate]
    counts = [total_customers, len(target_customers)]
    churn_counts = [churned_customers, target_churned]

    df = [
        {"구분": labels[0], "이탈율": values[0], "고객수": counts[0], "이탈고객수": churn_counts[0]},
        {"구분": labels[1], "이탈율": values[1], "고객수": counts[1], "이탈고객수": churn_counts[1]},
    ]

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
        title="고객 이탈율 비교",
    )
    fig.update_traces(textposition="outside", hovertemplate="<b>%{x}</b><br>고객 수: %{customdata[0]}명<br>이탈 고객 수: %{customdata[1]}명<br>이탈율: %{y:.1f}%<extra></extra>")
    fig.update_traces(customdata=list(zip(counts, churn_counts)))
    fig.update_layout(
        xaxis_title="구분",
        yaxis_title="이탈율 (%)",
        yaxis_range=[0, max(values) * 1.25 + 5],
        template="plotly_white",
        font=dict(family="Malgun Gothic, Arial, sans-serif"),
    )
    return fig


def build_channel_chart(consultations, satisfactions):
    satisfaction_map = {row["consult_id"]: row for row in satisfactions}
    channel_stats = {}

    for item in consultations:
        consult_id = item["consult_id"]
        channel = item["channel"]
        is_recontact = item.get("is_recontact")
        sat_row = satisfaction_map.get(consult_id)
        if not sat_row:
            continue
        try:
            csat = float(sat_row.get("csat", 0))
        except (TypeError, ValueError):
            continue
        stats = channel_stats.setdefault(channel, {"csat_sum": 0.0, "count": 0, "recontact": 0, "recontact_total": 0})
        stats["csat_sum"] += csat
        stats["count"] += 1
        stats["recontact_total"] += 1
        if is_recontact == "Y":
            stats["recontact"] += 1

    result = []
    for channel, stats in channel_stats.items():
        avg_csat = stats["csat_sum"] / stats["count"] if stats["count"] else 0.0
        recontact_rate = stats["recontact"] / stats["recontact_total"] * 100 if stats["recontact_total"] else 0.0
        result.append({
            "channel": channel,
            "csat_avg": round(avg_csat, 2),
            "recontact_rate": round(recontact_rate, 2),
        })
    result.sort(key=lambda x: x["csat_avg"])

    fig = go.Figure()
    fig.add_trace(go.Bar(x=[row["channel"] for row in result], y=[row["csat_avg"] for row in result], name="CSAT 평균", yaxis="y", marker_color="#4C78A8", hovertemplate="채널: %{x}<br>CSAT 평균: %{y:.2f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[row["channel"] for row in result], y=[row["recontact_rate"] for row in result], mode="lines+markers", name="재문의율 (%)", yaxis="y2", line=dict(color="#E45756", width=3), marker=dict(color="#E45756", size=8), hovertemplate="채널: %{x}<br>재문의율: %{y:.2f}%<extra></extra>"))
    fig.update_layout(title="채널별 CSAT 평균과 재문의율", xaxis_title="채널", yaxis_title="CSAT 평균", yaxis2=dict(title="재문의율 (%)", overlaying="y", side="right"), template="plotly_white", barmode="group", legend=dict(x=0.01, y=0.99), font=dict(family="Malgun Gothic, Arial, sans-serif"), hovermode="x unified")
    return fig


def build_recontact_chart(consultations, customers):
    customer_map = {row["customer_id"]: row for row in customers}
    customer_recontact_counts = {}
    for row in consultations:
        if row.get("is_recontact") == "Y":
            customer_id = row["customer_id"]
            customer_recontact_counts[customer_id] = customer_recontact_counts.get(customer_id, 0) + 1

    bucket_results = []
    for label in ["0회", "1회", "2회 이상"]:
        bucket_results.append({"구간": label, "고객수": 0, "이탈고객수": 0})

    for customer_id, customer in customer_map.items():
        recontact_count = customer_recontact_counts.get(customer_id, 0)
        bucket = "2회 이상" if recontact_count >= 2 else "1회" if recontact_count == 1 else "0회"
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

    fig = px.bar(
        bucket_results,
        x="구간",
        y="이탈율",
        color="구간",
        color_discrete_map={"0회": "#4C78A8", "1회": "#F58518", "2회 이상": "#E45756"},
        text=[f"{row['이탈율']:.1f}%" for row in bucket_results],
        labels={"구간": "재문의 횟수 구간", "이탈율": "이탈율 (%)"},
        title="재문의 횟수 구간별 이탈율",
        hover_data={"고객수": True, "이탈고객수": True, "이탈율": ":.2f"},
    )
    fig.add_hline(y=overall_rate, line_dash="dash", line_color="#2F4F4F", line_width=2, annotation_text=f"전체 평균 이탈율 {overall_rate:.1f}%", annotation_position="top left")
    fig.update_traces(textposition="outside", marker_line_width=0)
    fig.update_layout(template="plotly_white", yaxis_title="이탈율 (%)", xaxis_title="재문의 횟수 구간", yaxis_range=[0, max(row["이탈율"] for row in bucket_results) * 1.25 + 5], font=dict(family="Malgun Gothic, Arial, sans-serif"))
    return fig


def build_plan_chart(customers):
    plan_stats = {}
    for row in customers:
        plan = row.get("plan", "")
        stats = plan_stats.setdefault(plan, {"customer_count": 0, "churn_count": 0})
        stats["customer_count"] += 1
        if row.get("churn_yn") == "Y":
            stats["churn_count"] += 1

    data = []
    for plan, stats in plan_stats.items():
        data.append({"plan": plan, "customer_count": stats["customer_count"], "churn_count": stats["churn_count"], "churn_rate": round(stats["churn_count"] / stats["customer_count"] * 100, 2)})
    data.sort(key=lambda x: x["churn_rate"], reverse=True)

    fig = px.bar(
        data,
        x="plan",
        y="churn_rate",
        color="plan",
        text=[f"{row['churn_rate']:.1f}%" for row in data],
        labels={"plan": "요금제", "churn_rate": "이탈율 (%)"},
        title="요금제별 이탈율",
        hover_data={"customer_count": True, "churn_count": True, "churn_rate": ":.2f"},
        color_discrete_map={"베이직": "#E45756", "스탠다드": "#4C78A8", "프리미엄": "#F58518"},
    )
    fig.update_traces(textposition="outside", marker_line_width=0)
    fig.update_layout(template="plotly_white", yaxis_title="이탈율 (%)", xaxis_title="요금제", yaxis_range=[0, max(row["churn_rate"] for row in data) * 1.25 + 5], font=dict(family="Malgun Gothic, Arial, sans-serif"))
    return fig


def build_region_chart(customers):
    region_stats = {}
    for row in customers:
        region = row.get("region", "")
        stats = region_stats.setdefault(region, {"customer_count": 0, "churn_count": 0})
        stats["customer_count"] += 1
        if row.get("churn_yn") == "Y":
            stats["churn_count"] += 1

    data = []
    for region, stats in region_stats.items():
        data.append({"region": region, "customer_count": stats["customer_count"], "churn_count": stats["churn_count"], "churn_rate": round(stats["churn_count"] / stats["customer_count"] * 100, 2)})
    data.sort(key=lambda x: x["churn_rate"], reverse=True)

    fig = px.bar(
        data,
        x="region",
        y="churn_rate",
        color="region",
        text=[f"{row['churn_rate']:.1f}%" for row in data],
        labels={"region": "지역", "churn_rate": "이탈율 (%)"},
        title="지역별 이탈율",
        hover_data={"customer_count": True, "churn_count": True, "churn_rate": ":.2f"},
        color_discrete_map={"부산": "#E45756", "대구": "#E45756", "인천": "#4C78A8", "서울": "#4C78A8", "경기": "#4C78A8", "기타": "#4C78A8"},
    )
    fig.update_traces(textposition="outside", marker_line_width=0)
    fig.update_layout(template="plotly_white", yaxis_title="이탈율 (%)", xaxis_title="지역", yaxis_range=[0, max(row["churn_rate"] for row in data) * 1.25 + 5], font=dict(family="Malgun Gothic, Arial, sans-serif"))
    return fig


def build_tenure_scatter(customers, usage_rows):
    usage_by_customer = defaultdict(list)
    for row in usage_rows:
        usage_by_customer[row["customer_id"]].append(float(row["data_gb"]))

    data = []
    for customer in customers:
        customer_id = customer["customer_id"]
        join_date = customer.get("join_date")
        if join_date:
            join_dt = datetime.strptime(join_date, "%Y-%m-%d")
            end_dt = datetime.strptime("2024-12-31", "%Y-%m-%d")
            months = (end_dt.year - join_dt.year) * 12 + (end_dt.month - join_dt.month)
        else:
            months = None
        data_values = usage_by_customer.get(customer_id, [])
        avg_data_gb = round(sum(data_values) / len(data_values), 2) if data_values else None
        data.append({"customer_id": customer_id, "tenure_months": months, "avg_data_gb": avg_data_gb, "churn_yn": customer.get("churn_yn")})

    fig = px.scatter(
        data,
        x="tenure_months",
        y="avg_data_gb",
        color="churn_yn",
        color_discrete_map={"Y": "#E45756", "N": "#4C78A8"},
        hover_data={"customer_id": True, "tenure_months": True, "avg_data_gb": True, "churn_yn": True},
        labels={"tenure_months": "가입기간(개월)", "avg_data_gb": "평균 데이터 사용량(GB)", "churn_yn": "이탈 여부"},
        title="가입기간과 평균 데이터 사용량 산점도",
    )
    fig.update_layout(template="plotly_white", font=dict(family="Malgun Gothic, Arial, sans-serif"))
    return fig


def main():
    st.set_page_config(page_title="고객은 왜 이탈하는가", layout="wide")
    st.title("고객은 왜 이탈하는가 — 이탈 원인 진단 대시보드")

    customers, vocs, consultations, satisfactions, usage_rows = load_data()
    total_customers, churned_customers, overall_rate = build_overall_metrics(customers)

    cols = st.columns(3)
    cols[0].metric("전체 고객 수", f"{total_customers}명")
    cols[1].metric("이탈 고객 수", f"{churned_customers}명")
    cols[2].metric("전체 이탈율", f"{overall_rate:.1f}%")

    st.subheader("① VOC로 본 이탈")
    st.plotly_chart(build_voc_chart(customers, vocs), use_container_width=True)

    st.subheader("② 채널·만족도로 본 이탈")
    st.plotly_chart(build_channel_chart(consultations, satisfactions), use_container_width=True)

    st.subheader("③ 재문의 반복으로 본 이탈")
    st.plotly_chart(build_recontact_chart(consultations, customers), use_container_width=True)

    st.subheader("④ 요금제로 본 이탈")
    st.plotly_chart(build_plan_chart(customers), use_container_width=True)

    st.subheader("⑤ 지역으로 본 이탈")
    st.plotly_chart(build_region_chart(customers), use_container_width=True)
    st.caption("인천은 표본이 53건이지만 이탈 1건뿐이라는 점을 참고하세요.")

    st.subheader("⑥ 가입기간·이용량으로 본 이탈")
    st.plotly_chart(build_tenure_scatter(customers, usage_rows), use_container_width=True)


if __name__ == "__main__":
    main()
