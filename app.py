import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
REPORT_PATH = BASE_DIR / "report" / "고객서비스_만족도개선_리포트.md"

# 상담원 관점 섹션용 스냅샷. BigQuery `project1_day1.agents` 에서 미리 내려받아 둔 파일이며,
# 없으면 팀 필터와 교육이수 비교는 자동으로 비활성화된다(DEPLOY.md 3번 항목 참고).
AGENTS_SNAPSHOT = DATA_DIR / "agents_snapshot.csv"
AGENT_CONSULT_SNAPSHOT = DATA_DIR / "agent_consultations_snapshot.csv"
SNAPSHOT_DATE = "2026-07-25"

# 응답 수가 적은 상담원은 NPS·CSAT 평균이 크게 흔들리므로 제외
MIN_AGENT_RESPONSES = 10

ALL_TEAMS = "전체"


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


def calculate_nps(scores):
    """NPS = 추천고객(9~10) 비율 - 비추천고객(0~6) 비율, 단위는 포인트."""
    if not scores:
        return 0.0
    promoters = sum(1 for s in scores if s >= 9)
    detractors = sum(1 for s in scores if s <= 6)
    return round((promoters - detractors) / len(scores) * 100, 1)


def load_agent_snapshot():
    """상담원 속성(팀·직원만족도·초과근무·교육이수) 스냅샷을 읽는다.

    로컬 CSV 5개에는 agent_id 만 있고 상담원 마스터 테이블이 없다.
    팀·직원만족도·교육이수는 BigQuery `project1_day1.agents` 에만 있으므로
    스냅샷 파일이 있을 때만 채워지고, 없으면 빈 dict 를 돌려준다.
    """
    attrs = {}
    if AGENTS_SNAPSHOT.exists():
        for row in read_csv_rows(AGENTS_SNAPSHOT):
            agent_id = (row.get("agent_id") or "").strip()
            if not agent_id:
                continue
            attrs[agent_id] = {
                "team": (row.get("team") or "").strip() or None,
                "agent_satisfaction": to_float(row.get("agent_satisfaction")),
                "overtime_hours_avg": to_float(row.get("overtime_hours_avg")),
                "training_completed_yn": (row.get("training_completed_yn") or "").strip() or None,
            }

    # 교육이수 여부는 가이드 SQL 상 상담 스냅샷 쪽에 들어있어, 위에서 못 채웠으면 여기서 보완한다.
    if AGENT_CONSULT_SNAPSHOT.exists():
        for row in read_csv_rows(AGENT_CONSULT_SNAPSHOT):
            agent_id = (row.get("agent_id") or "").strip()
            if not agent_id:
                continue
            item = attrs.setdefault(agent_id, {
                "team": None,
                "agent_satisfaction": None,
                "overtime_hours_avg": None,
                "training_completed_yn": None,
            })
            if not item.get("team"):
                item["team"] = (row.get("team") or "").strip() or None
            if not item.get("training_completed_yn"):
                item["training_completed_yn"] = (row.get("training_completed_yn") or "").strip() or None

    return attrs


def to_float(value):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def build_agent_metrics(consultations, satisfactions, agent_attrs):
    """상담원별 NPS·CSAT·업무부하·재문의율을 로컬 CSV 에서 재계산한다."""
    agent_by_consult = {row["consult_id"]: (row.get("agent_id") or "").strip() for row in consultations}

    workload = {}
    for row in consultations:
        agent_id = (row.get("agent_id") or "").strip()
        if not agent_id:
            continue
        stats = workload.setdefault(agent_id, {"consult_count": 0, "total_min": 0, "recontact": 0})
        stats["consult_count"] += 1
        try:
            stats["total_min"] += int(row.get("duration_min") or 0)
        except (TypeError, ValueError):
            pass
        if row.get("is_recontact") == "Y":
            stats["recontact"] += 1

    nps_scores = defaultdict(list)
    csat_scores = defaultdict(list)
    for row in satisfactions:
        agent_id = agent_by_consult.get(row.get("consult_id", ""))
        if not agent_id:
            continue
        nps_raw = (row.get("nps") or "").strip()
        if nps_raw:
            try:
                nps_scores[agent_id].append(int(nps_raw))
            except ValueError:
                pass
        csat_raw = (row.get("csat") or "").strip()
        if csat_raw:
            try:
                csat_scores[agent_id].append(int(csat_raw))
            except ValueError:
                pass

    agents = []
    excluded = []
    for agent_id in sorted(set(workload) | set(nps_scores) | set(csat_scores)):
        stats = workload.get(agent_id, {"consult_count": 0, "total_min": 0, "recontact": 0})
        attrs = agent_attrs.get(agent_id, {})
        nps_list = nps_scores.get(agent_id, [])
        csat_list = csat_scores.get(agent_id, [])
        item = {
            "agent_id": agent_id,
            "team": attrs.get("team"),
            "agent_satisfaction": attrs.get("agent_satisfaction"),
            "overtime_hours_avg": attrs.get("overtime_hours_avg"),
            "training_completed_yn": attrs.get("training_completed_yn"),
            "nps": calculate_nps(nps_list),
            "nps_scores": nps_list,
            "csat_scores": csat_list,
            "csat_avg": round(sum(csat_list) / len(csat_list), 2) if csat_list else None,
            "workload_hours": round(stats["total_min"] / 60, 1),
            "consult_count": stats["consult_count"],
            "recontact_rate": round(stats["recontact"] / stats["consult_count"] * 100, 1) if stats["consult_count"] else 0.0,
            "response_count": len(nps_list),
            "csat_response_count": len(csat_list),
        }
        # NPS·CSAT 둘 중 하나라도 표본이 충분하면 표시 대상으로 둔다.
        if max(len(nps_list), len(csat_list)) >= MIN_AGENT_RESPONSES:
            agents.append(item)
        else:
            excluded.append(item)

    return agents, excluded


def available_teams(agents):
    return sorted({a["team"] for a in agents if a.get("team")})


def filter_by_team(agents, team):
    if team == ALL_TEAMS:
        return agents
    return [a for a in agents if a.get("team") == team]


def build_nps_gauge(agents, label):
    """선택 범위의 고객 NPS 게이지. 상담원별 원점수를 모두 합쳐서 계산한다."""
    pooled = [s for a in agents for s in a["nps_scores"]]
    nps = calculate_nps(pooled)

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=nps,
        number={"suffix": "점", "font": {"size": 40}},
        title={
            "text": f"{label} 고객 NPS<br><span style='font-size:12px;color:#666'>"
                    f"응답 {len(pooled):,}건 · 상담원 {len(agents)}명</span>",
            "font": {"size": 16},
        },
        gauge={
            "axis": {"range": [-100, 100], "tickmode": "array", "tickvals": [-100, -50, 0, 50, 100], "tickfont": {"size": 11}},
            "bar": {"color": "#2F4F4F", "thickness": 0.28},
            "borderwidth": 1,
            "bordercolor": "#D9D9D9",
            "steps": [
                {"range": [-100, -50], "color": "#E45756"},
                {"range": [-50, 0], "color": "#F5B0AF"},
                {"range": [0, 50], "color": "#EDF3F8"},
                {"range": [50, 100], "color": "#BBD3E8"},
            ],
            "threshold": {"line": {"color": "#333333", "width": 3}, "thickness": 0.85, "value": 0},
        },
    ))
    fig.update_layout(
        template="plotly_white",
        font=dict(family="Malgun Gothic, Arial, sans-serif"),
        height=250,
        margin=dict(t=70, b=10, l=20, r=20),
    )
    return fig, nps


def build_agent_card(label, agent, reference):
    """최고/중앙값/최저 상담원 카드. 선택 범위 NPS 대비 델타를 함께 보여준다."""
    fig = go.Figure(go.Indicator(
        mode="number+delta",
        value=agent["nps"],
        number={"suffix": "점", "font": {"size": 34}},
        delta={
            "reference": reference,
            "valueformat": ".1f",
            "increasing": {"color": "#4C78A8"},
            "decreasing": {"color": "#E45756"},
            "font": {"size": 14},
        },
        title={
            "text": f"{label}<br><span style='font-size:12px;color:#666'>"
                    f"{agent['agent_id']} · {agent['response_count']}건</span>",
            "font": {"size": 15},
        },
    ))
    fig.update_layout(
        template="plotly_white",
        font=dict(family="Malgun Gothic, Arial, sans-serif"),
        height=250,
        margin=dict(t=70, b=10, l=20, r=20),
    )
    return fig


def pearson_r(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return None
    return cov / (var_x * var_y) ** 0.5


def least_squares_line(xs, ys):
    """추세선용 최소제곱 직선. 표본이 2개 미만이거나 x가 한 점이면 None."""
    n = len(xs)
    if n < 2:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x == 0:
        return None
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / var_x
    intercept = mean_y - slope * mean_x
    x_min, x_max = min(xs), max(xs)
    return [x_min, x_max], [intercept + slope * x_min, intercept + slope * x_max]


def build_burnout_scatter(agents, label):
    """번아웃 대리지표와 CSAT 평균의 관계.

    실제 초과근무(overtime_hours_avg)가 스냅샷에 있으면 그 값을, 없으면
    총 상담시간을 번아웃 대리지표로 x축에 쓴다.
    """
    points = [a for a in agents if a["csat_avg"] is not None]
    has_overtime = bool(points) and all(a.get("overtime_hours_avg") is not None for a in points)

    if has_overtime:
        x_col, x_label = "overtime_hours_avg", "평균 초과근무 시간 (시간)"
        subtitle = "실제 초과근무 데이터 기준"
    else:
        x_col, x_label = "workload_hours", "업무부하 · 총 상담시간 (시간)"
        subtitle = "※ 초과근무 데이터가 없어 '총 상담시간'을 번아웃 대리지표로 사용"

    xs = [a[x_col] for a in points]
    ys = [a["csat_avg"] for a in points]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=xs,
        y=ys,
        mode="markers",
        name="상담원",
        marker=dict(size=13, color="#4C78A8", line=dict(width=1, color="white")),
        customdata=[[a["agent_id"], a["team"] or "-", a["consult_count"], a["csat_response_count"]] for a in points],
        hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>"
                      + x_label + ": %{x:.1f}<br>CSAT 평균: %{y:.2f}<br>"
                      "상담 건수: %{customdata[2]}건<br>CSAT 응답: %{customdata[3]}건<extra></extra>",
    ))

    line = least_squares_line(xs, ys)
    if line:
        fig.add_trace(go.Scatter(x=line[0], y=line[1], mode="lines", name="추세선",
                                 line=dict(color="#E45756", width=2), hoverinfo="skip"))

    r = pearson_r(xs, ys)
    r_text = f"<b>r = {r:.2f}</b>" if r is not None else "<b>r 계산 불가</b><br><span style='font-size:11px'>표본 부족</span>"
    fig.add_annotation(
        xref="paper", yref="paper", x=0.99, y=0.98, xanchor="right", yanchor="top",
        text=r_text, showarrow=False, font=dict(size=16, color="#E45756"),
        bgcolor="rgba(255,255,255,0.85)", bordercolor="#E45756", borderwidth=1, borderpad=6,
    )

    fig.update_layout(
        template="plotly_white",
        font=dict(family="Malgun Gothic, Arial, sans-serif"),
        title=f"{label} · 번아웃과 CSAT 평균<br><span style='font-size:11px;color:#888'>{subtitle}</span>",
        xaxis_title=x_label,
        yaxis_title="CSAT 평균 (1~5점)",
        height=420,
        margin=dict(t=90),
        showlegend=False,
    )
    return fig, len(points)


def build_training_chart(agents, label):
    """교육이수 여부별 CSAT 평균·재문의율 비교. 표본 수를 함께 노출한다."""
    groups = {"이수": [], "미이수": []}
    for agent in agents:
        flag = agent.get("training_completed_yn")
        if flag == "Y":
            groups["이수"].append(agent)
        elif flag == "N":
            groups["미이수"].append(agent)

    rows = []
    for name, members in groups.items():
        pooled_csat = [s for a in members for s in a["csat_scores"]]
        total_consults = sum(a["consult_count"] for a in members)
        total_recontact = sum(a["consult_count"] * a["recontact_rate"] / 100 for a in members)
        rows.append({
            "구분": name,
            "상담원수": len(members),
            "csat_avg": round(sum(pooled_csat) / len(pooled_csat), 2) if pooled_csat else 0.0,
            "응답수": len(pooled_csat),
            "재문의율": round(total_recontact / total_consults * 100, 1) if total_consults else 0.0,
        })

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[r["구분"] for r in rows],
        y=[r["csat_avg"] for r in rows],
        marker_color=["#4C78A8", "#E45756"],
        text=[f"{r['csat_avg']:.2f}" for r in rows],
        textposition="outside",
        customdata=[[r["상담원수"], r["응답수"], r["재문의율"]] for r in rows],
        hovertemplate="<b>%{x}</b><br>CSAT 평균: %{y:.2f}<br>"
                      "상담원 %{customdata[0]}명 · 응답 %{customdata[1]}건<br>"
                      "재문의율: %{customdata[2]:.1f}%<extra></extra>",
    ))
    max_csat = max([r["csat_avg"] for r in rows] or [0])
    fig.update_layout(
        template="plotly_white",
        font=dict(family="Malgun Gothic, Arial, sans-serif"),
        title=f"{label} · 교육이수 여부별 CSAT 평균",
        xaxis_title="교육이수 여부",
        yaxis_title="CSAT 평균 (1~5점)",
        yaxis_range=[0, max_csat * 1.25 + 0.5],
        height=420,
        margin=dict(t=90),
    )
    return fig, rows


def render_agent_section(consultations, satisfactions):
    """⑦ 상담원 관점 섹션. 팀 필터 하나로 07~09번 컴포넌트를 함께 제어한다."""
    st.subheader("⑦ 상담원 관점: 직원만족도와 고객 경험")

    agent_attrs = load_agent_snapshot()
    agents, excluded = build_agent_metrics(consultations, satisfactions, agent_attrs)
    teams = available_teams(agents)

    if teams:
        st.caption(f"🟡 스냅샷 데이터 · `data/agents_snapshot.csv` 기준 (SNAPSHOT_DATE {SNAPSHOT_DATE})")
    else:
        st.caption(
            "⚪ 팀·직원만족도·교육이수 데이터 없음 — 로컬 CSV 5개에는 `agent_id` 만 있습니다. "
            "`data/agents_snapshot.csv` 를 넣으면 팀 필터와 교육이수 비교가 자동으로 켜집니다 (DEPLOY.md 3번 참고)."
        )

    selected_team = st.radio(
        "팀 선택",
        [ALL_TEAMS] + teams,
        horizontal=True,
        key="agent_team_filter",
        disabled=not teams,
        help="팀 데이터가 없으면 전체만 선택할 수 있습니다." if not teams else None,
    )

    scoped = filter_by_team(agents, selected_team)
    label = "전체" if selected_team == ALL_TEAMS else selected_team

    if not scoped:
        st.info(f"{label}에 표시할 상담원이 없습니다. (CSAT·NPS 응답 {MIN_AGENT_RESPONSES}건 이상인 상담원만 집계)")
        return

    # 07번 — 스코어카드를 가로로 나란히
    gauge_fig, scope_nps = build_nps_gauge(scoped, label)
    ranked = sorted([a for a in scoped if a["response_count"] > 0], key=lambda x: x["nps"], reverse=True)

    cols = st.columns(4)
    cols[0].plotly_chart(gauge_fig, use_container_width=True)
    if ranked:
        cards = [
            ("최고 상담원", ranked[0]),
            ("중앙값 상담원", ranked[len(ranked) // 2]),
            ("최저 상담원", ranked[-1]),
        ]
        for col, (card_label, agent) in zip(cols[1:], cards):
            col.plotly_chart(build_agent_card(card_label, agent, scope_nps), use_container_width=True)
    else:
        cols[1].info("NPS 응답이 있는 상담원이 없습니다.")

    st.caption(
        f"※ 직원 대상 eNPS가 아니라, 상담을 경험한 **고객**이 응답한 NPS입니다 — "
        f"`data_satisfaction.csv` 의 nps를 `agent_id` 로 집계한 값입니다. "
        f"표시 대상 상담원 {len(scoped)}명"
        + (f" · 응답 {MIN_AGENT_RESPONSES}건 미만으로 제외 {len(excluded)}명" if excluded else "")
    )

    # 08번·09번 — 아래에 나란히
    lower = st.columns(2)
    with lower[0]:
        scatter_fig, point_count = build_burnout_scatter(scoped, label)
        st.plotly_chart(scatter_fig, use_container_width=True)
        if point_count < 3:
            st.caption(f"표본 {point_count}명 — 추세선과 상관계수는 참고용으로만 보세요.")

    with lower[1]:
        if any(a.get("training_completed_yn") in ("Y", "N") for a in scoped):
            training_fig, rows = build_training_chart(scoped, label)
            st.plotly_chart(training_fig, use_container_width=True)
            counts = " · ".join(f"{r['구분']} {r['상담원수']}명" for r in rows)
            st.caption(f"{counts} — 교육이수 여부는 입사 시점과 얽혀 있어 개인 역량 지표로 읽지 마세요.")
        else:
            st.info(
                "교육이수 비교를 그릴 데이터가 없습니다.\n\n"
                "`training_completed_yn` 은 BigQuery `project1_day1.agents` 에만 있어, "
                "스냅샷 CSV를 넣어야 표시됩니다."
            )

    if len(scoped) <= 7:
        st.warning(
            f"⚠️ {label} 표본은 상담원 {len(scoped)}명입니다. 리포트 §4.5 기준으로 "
            "한 사람의 응답이 팀 NPS를 28.6~33.3%p 움직이므로, 팀 간 순위 비교의 근거로 쓰기에는 부족합니다."
        )


def split_frontmatter(text):
    """마크다운 앞머리 YAML 블록을 본문과 분리한다.

    st.markdown 은 YAML 을 모르기 때문에, 그냥 넘기면 `---` 가 구분선으로,
    그 아래 title/date 줄이 큰 제목으로 잘못 렌더된다.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            meta = {}
            for line in lines[1:index]:
                if ":" in line:
                    key, value = line.split(":", 1)
                    meta[key.strip()] = value.strip().strip('"')
            return meta, "\n".join(lines[index + 1:]).lstrip("\n")

    return {}, text


@st.cache_data(show_spinner=False)
def load_report():
    """개선 제안 리포트 마크다운을 읽어 (메타데이터, 본문) 으로 돌려준다."""
    if not REPORT_PATH.exists():
        return None, None
    return split_frontmatter(REPORT_PATH.read_text(encoding="utf-8"))


def kpi_card(label, value, accent, sub=None):
    """스타일 지표 카드 (HTML). accent는 #RRGGBB 형식."""
    sub_html = f'<div style="color:#9aa0a6;font-size:12px;margin-top:3px;">{sub}</div>' if sub else ""
    return (
        f'<div style="background:{accent}12;border:1px solid {accent}33;border-left:5px solid {accent};'
        f'border-radius:10px;padding:14px 18px;">'
        f'<div style="color:#6b7280;font-size:13px;">{label}</div>'
        f'<div style="font-size:30px;font-weight:800;color:{accent};margin-top:3px;line-height:1.1;">{value}</div>'
        f'{sub_html}</div>'
    )


def render_dashboard_tab():
    """대시보드 탭 — 지표 카드와 ①~⑥ 차트, ⑦ 상담원 관점 섹션."""
    st.markdown("##### 🔹 소주제: 고객 이탈 분석 — VOC·채널·요금제·지역 등으로 본 이탈 (이전 분석)")
    customers, vocs, consultations, satisfactions, usage_rows = load_data()
    total_customers, churned_customers, overall_rate = build_overall_metrics(customers)

    cols = st.columns(3)
    cols[0].markdown(kpi_card("전체 고객 수", f"{total_customers:,}명", "#4C78A8"), unsafe_allow_html=True)
    cols[1].markdown(kpi_card("이탈 고객 수", f"{churned_customers:,}명", "#F58518"), unsafe_allow_html=True)
    cols[2].markdown(kpi_card("전체 이탈율", f"{overall_rate:.1f}%", "#E45756", sub=f"이탈 {churned_customers}명 / 전체 {total_customers}명"), unsafe_allow_html=True)
    st.write("")

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

    st.divider()
    render_agent_section(consultations, satisfactions)


def render_report_tab():
    """개선 제안 리포트 탭 — 마크다운 전문을 그대로 렌더한다."""
    st.markdown("##### 🔹 소주제: 고객 이탈 개선 제안 리포트")
    meta, body = load_report()

    if body is None:
        st.error(
            f"리포트 파일을 찾을 수 없습니다: `{REPORT_PATH.relative_to(BASE_DIR)}`\n\n"
            "`report/` 폴더가 저장소에 함께 올라갔는지 확인해 주세요."
        )
        return

    caption_parts = []
    if meta.get("date"):
        caption_parts.append(f"작성일 {meta['date']}")
    caption_parts.append(f"출처 `{REPORT_PATH.relative_to(BASE_DIR).as_posix()}`")
    st.caption(" · ".join(caption_parts))

    # 가독성: 줄간격·헤더 간격·표 글자크기 (markdown 렌더에 가볍게 적용)
    st.markdown(
        "<style>"
        "div[data-testid='stMarkdownContainer'] p,"
        "div[data-testid='stMarkdownContainer'] li { line-height: 1.8; }"
        "div[data-testid='stMarkdownContainer'] h2 { margin-top: 1.6em; padding-bottom:.25em; border-bottom:1px solid #e6e6e6; }"
        "div[data-testid='stMarkdownContainer'] h3 { margin-top: 1.1em; color:#2E5A88; }"
        "div[data-testid='stMarkdownContainer'] table { font-size: 14px; }"
        "</style>",
        unsafe_allow_html=True,
    )
    st.info(
        "**한눈에 보기** — 2024년 상담 1,320건 전수 분석 · 재문의율 **21.4%**(개선기준 20% 초과) · "
        "재문의가 갈리는 축은 **상담 채널** 하나(비동기 채널이 전화의 2배 이상) · "
        "상담원·카테고리는 유의하지 않음 · 직원만족도·번아웃은 고객경험과 유의하게 연결."
    )
    st.divider()

    # <sup> 각주 표기가 있어 HTML 을 허용한다. 저장소 안의 자체 작성 파일만 읽는다.
    st.markdown(body, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# 마케팅 채널 효율성 분석 (4주차 프로젝트: 마케팅 채널 효율성 분석)
# 데이터: data/data_marketing_spend.csv (채널×월, 2019-01~2024-06)
#        data/marketing_campaigns.csv (캠페인, 2024-05~07, 예산 有)
# 결합은 파일/DB에 저장하지 않고 여기서 매번 읽어 합친다(교안 방식).
# ─────────────────────────────────────────────────────────────
MARKETING_SPEND = DATA_DIR / "data_marketing_spend.csv"
MARKETING_CAMPAIGNS = DATA_DIR / "marketing_campaigns.csv"

COLOR_BASE = "#4C78A8"   # 기본 파랑
COLOR_WARN = "#E45756"   # 강조 빨강


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def load_marketing():
    spend = read_csv_rows(MARKETING_SPEND) if MARKETING_SPEND.exists() else []
    campaigns = read_csv_rows(MARKETING_CAMPAIGNS) if MARKETING_CAMPAIGNS.exists() else []
    return spend, campaigns


def verify_overlap(spend, campaigns):
    """2024-05·06월: spend(월지출) vs campaigns(실집행 합)이 일치하는지 대조."""
    camp_sum = defaultdict(int)
    for row in campaigns:
        if row["월"] in ("2024-05", "2024-06"):
            camp_sum[(row["월"], row["채널"])] += _to_int(row["실집행"])
    ok = total = 0
    for row in spend:
        if row["month"] in ("2024-05", "2024-06"):
            total += 1
            if _to_int(row["spend"]) == camp_sum.get((row["month"], row["channel"])):
                ok += 1
    return ok, total


def build_cac_chart(spend):
    """채널별 유입 1건당 비용(=지출합/유입합). 낮을수록 효율적."""
    agg = {}
    for row in spend:
        stats = agg.setdefault(row["channel"], {"spend": 0, "signups": 0})
        stats["spend"] += _to_int(row["spend"])
        stats["signups"] += _to_int(row["signups"])
    rows = []
    for channel, stats in agg.items():
        cac = round(stats["spend"] / stats["signups"]) if stats["signups"] else 0
        rows.append({"채널": channel, "유입1건당비용": cac, "지출합": stats["spend"], "유입합": stats["signups"]})
    rows.sort(key=lambda r: r["유입1건당비용"])  # 싼 채널이 왼쪽
    worst = max(rows, key=lambda r: r["유입1건당비용"])["채널"] if rows else None
    colors = [COLOR_WARN if r["채널"] == worst else COLOR_BASE for r in rows]

    fig = px.bar(
        rows, x="채널", y="유입1건당비용",
        text=[f"{r['유입1건당비용']:,}원" for r in rows],
        title="① 채널별 유입 1건당 비용 (2019-01~2024-06)",
        hover_data={"지출합": ":,", "유입합": True, "유입1건당비용": ":,"},
    )
    fig.update_traces(marker_color=colors, textposition="outside")
    fig.update_layout(
        yaxis_title="유입 1건당 비용 (원)", xaxis_title="채널",
        template="plotly_white", font=dict(family="Malgun Gothic, Arial, sans-serif"),
        showlegend=False,
    )
    return fig


def build_execution_chart(campaigns):
    """완료 캠페인 기준 채널별 예산 집행률(=실집행/예산×100). 100% 초과=예산 초과."""
    bc = {}
    for row in campaigns:
        if row["is_completed"] != "True":
            continue
        stats = bc.setdefault(row["채널"], {"budget": 0, "actual": 0})
        stats["budget"] += _to_int(row["예산"])
        stats["actual"] += _to_int(row["실집행"])
    rows = []
    for channel, stats in bc.items():
        rate = round(stats["actual"] / stats["budget"] * 100) if stats["budget"] else 0
        rows.append({"채널": channel, "집행률": rate, "예산": stats["budget"], "실집행": stats["actual"]})
    rows.sort(key=lambda r: -r["집행률"])
    colors = [COLOR_WARN if r["집행률"] > 100 else COLOR_BASE for r in rows]

    fig = px.bar(
        rows, x="채널", y="집행률",
        text=[f"{r['집행률']}%" for r in rows],
        title="② 채널별 예산 집행률 (완료 캠페인, 2024)",
        hover_data={"예산": ":,", "실집행": ":,", "집행률": True},
    )
    fig.update_traces(marker_color=colors, textposition="outside")
    fig.add_hline(y=100, line_dash="dash", line_color="gray", annotation_text="예산 100%")
    fig.update_layout(
        yaxis_title="집행률 (%)", xaxis_title="채널",
        template="plotly_white", font=dict(family="Malgun Gothic, Arial, sans-serif"),
        showlegend=False,
    )
    return fig


def build_spend_trend_chart(spend, campaigns):
    """월별 총 마케팅 지출 추세. 2024-07은 campaigns 실집행으로 이어붙임."""
    monthly = defaultdict(int)
    for row in spend:
        monthly[row["month"]] += _to_int(row["spend"])
    for row in campaigns:
        if row["월"] == "2024-07":
            monthly["2024-07"] += _to_int(row["실집행"])
    months = sorted(monthly)
    rows = [{"월": m, "총지출": monthly[m]} for m in months]

    fig = px.line(
        rows, x="월", y="총지출", markers=False,
        title="③ 월별 총 마케팅 지출 추세 (2019-01~2024-07)",
    )
    fig.update_traces(line_color=COLOR_BASE)
    fig.update_layout(
        yaxis_title="총 지출 (원)", xaxis_title="월",
        template="plotly_white", font=dict(family="Malgun Gothic, Arial, sans-serif"),
    )
    return fig


def _channel_stats(spend):
    """채널별 지출합·유입합·유입1건당비용(CAC)."""
    agg = {}
    for row in spend:
        s = agg.setdefault(row["channel"], {"spend": 0, "signups": 0})
        s["spend"] += _to_int(row["spend"])
        s["signups"] += _to_int(row["signups"])
    for s in agg.values():
        s["cac"] = s["spend"] / s["signups"] if s["signups"] else 0
    return agg


def build_reallocation_chart(spend):
    """[가상 H1] SNS광고 예산의 30%를 고효율 2채널로 재배분 시 총 유입(선형 가정)."""
    stats = _channel_stats(spend)
    move_from, targets, ratio = "SNS광고", ["지인추천", "자사앱푸시"], 0.30
    move_amt = stats[move_from]["spend"] * ratio

    new_spend = {ch: s["spend"] for ch, s in stats.items()}
    new_spend[move_from] -= move_amt
    for t in targets:
        new_spend[t] += move_amt / len(targets)

    current = sum(s["signups"] for s in stats.values())
    projected = sum((new_spend[ch] / stats[ch]["cac"]) if stats[ch]["cac"] else 0 for ch in stats)

    rows = [
        {"시나리오": "현재", "총 유입(추정)": round(current)},
        {"시나리오": "재배분(가상)", "총 유입(추정)": round(projected)},
    ]
    fig = px.bar(
        rows, x="시나리오", y="총 유입(추정)",
        text=[f"{r['총 유입(추정)']:,}건" for r in rows], color="시나리오",
        color_discrete_map={"현재": COLOR_BASE, "재배분(가상)": "#59A14F"},
        title="🧪 H1. 예산 재배분 What-if (가상 · 선형 가정)",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        yaxis_title="총 유입 (건, 추정)", xaxis_title="",
        template="plotly_white", font=dict(family="Malgun Gothic, Arial, sans-serif"),
        showlegend=False,
    )
    return fig


def build_diminishing_chart(spend):
    """[가상 H2] 저비용 채널 예산 확대 시 수확체감(제곱근 가정)."""
    stats = _channel_stats(spend)
    channels = ["지인추천", "자사앱푸시"]
    mults = [1, 1.5, 2, 2.5, 3, 4, 5]
    rows = []
    for ch in channels:
        base = stats[ch]["signups"]
        for m in mults:
            rows.append({"채널": ch, "예산배수": m, "유입(가상)": round(base * (m ** 0.6))})
    # 선형(2배 예산=2배 유입) 참조선 — 지인추천 기준
    base_ref = stats["지인추천"]["signups"]
    for m in mults:
        rows.append({"채널": "선형 가정(참조)", "예산배수": m, "유입(가상)": round(base_ref * m)})

    fig = px.line(
        rows, x="예산배수", y="유입(가상)", color="채널", markers=True,
        title="🧪 H2. 저비용 채널 예산 확대 시 수확체감 (가상)",
        color_discrete_map={"지인추천": COLOR_BASE, "자사앱푸시": "#59A14F", "선형 가정(참조)": "#BAB0AC"},
    )
    fig.update_layout(
        yaxis_title="유입 (건, 가상)", xaxis_title="예산 배수 (현재=1)",
        template="plotly_white", font=dict(family="Malgun Gothic, Arial, sans-serif"),
    )
    return fig


def render_marketing_tab():
    """채널 효율 탭 — 유입 1건당 비용·집행률·지출 추세."""
    st.markdown("##### 🔹 소주제: 마케팅 채널 효율성 — 채널별 유입 1건당 비용 · 예산 집행률")
    spend, campaigns = load_marketing()
    if not spend or not campaigns:
        st.warning(
            "마케팅 데이터 파일이 없습니다. "
            "`data/data_marketing_spend.csv` 와 `data/marketing_campaigns.csv` 가 있는지 확인해 주세요."
        )
        return

    ok, total = verify_overlap(spend, campaigns)
    if total and ok == total:
        st.caption(f"🟢 데이터 대조검증: 2024-05·06월 {ok}/{total} 채널×월 일치 (두 데이터가 맞물림)")
    else:
        st.caption(f"🟡 데이터 대조검증: {ok}/{total} 일치 — 확인 필요")

    st.plotly_chart(build_cac_chart(spend), use_container_width=True)
    st.caption("돈을 가장 많이 쓴 SNS광고가 유입 1건당 비용은 최고(약 15만원) — 지인추천의 약 52배. "
               "채널별 유입 표본이 60~110건으로 크지 않아 '경향'으로 해석하세요.")

    st.plotly_chart(build_execution_chart(campaigns), use_container_width=True)
    st.caption("100% 초과(빨강)는 예산보다 더 쓴 채널. 지인추천·제휴사는 83%로 예산 여력이 있음.")

    st.plotly_chart(build_spend_trend_chart(spend, campaigns), use_container_width=True)
    st.caption("2024-07월분은 캠페인 데이터(실집행)를 이어붙인 값입니다.")

    st.info("💡 **시사점**: 비효율(고비용) 채널 예산을 고효율(저비용) 채널로 재배분할 여지가 있습니다. "
            "단 표본이 작아 추세 모니터링을 병행하세요.")

    # ── 가상 시나리오 (가설 H1·H2) ──────────────────────────────
    st.divider()
    st.markdown("### 🧪 가상 시나리오 (가설 시뮬레이션)")
    st.warning(
        "⚠️ 아래 두 차트는 **실제 데이터가 아니라 '가정'에 기반한 가상 시뮬레이션**입니다. "
        "의사결정 사고(what-if)를 보여주기 위한 예시이며, 실제 집행 결과가 아닙니다."
    )

    st.plotly_chart(build_reallocation_chart(spend), use_container_width=True)
    st.caption(
        "**H1 · 예산 재배분**: SNS광고 예산의 30%를 고효율 채널(지인추천·자사앱푸시)로 옮기고 "
        "각 채널의 유입 1건당 비용이 그대로라고 **선형 가정**하면 같은 예산으로 총 유입이 크게 늘어납니다. "
        "다만 이는 이상적 상한선 — 현실은 아래 H2처럼 수확체감이 작용합니다."
    )

    st.plotly_chart(build_diminishing_chart(spend), use_container_width=True)
    st.caption(
        "**H2 · 수확체감**: 저비용 채널이라도 예산을 2배로 늘린다고 유입이 2배가 되진 않습니다"
        "(제곱근 모델 가정). 회색 '선형 가정' 선과 벌어지는 만큼이 현실의 한계입니다. "
        "→ H1의 재배분 효과는 **상한선으로만** 참고하고, 소규모로 시험 집행하며 확인하는 것이 안전합니다."
    )


def render_banner():
    """상단 헤드라인 배너 — 그라데이션 + 핵심 KPI 칩."""
    spend, campaigns = load_marketing()
    chips = ""
    if spend and campaigns:
        stats = _channel_stats(spend)
        scored = [c for c in stats if stats[c]["signups"]]
        best = min(scored, key=lambda c: stats[c]["cac"])
        worst = max(scored, key=lambda c: stats[c]["cac"])
        comp = [r for r in campaigns if r["is_completed"] == "True"]
        tb = sum(_to_int(r["예산"]) for r in comp)
        ta = sum(_to_int(r["실집행"]) for r in comp)
        rate = round(ta / tb * 100) if tb else 0

        def chip(text):
            return (f'<span style="background:rgba(255,255,255,.18);padding:7px 14px;'
                    f'border-radius:18px;font-size:13px;white-space:nowrap;">{text}</span>')

        chips = (
            '<div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap;">'
            + chip(f"🏆 최고효율 {best} {round(stats[best]['cac']):,}원")
            + chip(f"💸 최저효율 {worst} {round(stats[worst]['cac']):,}원")
            + chip(f"📊 전체 집행률 {rate}%")
            + "</div>"
        )

    st.markdown(
        '<div style="background:linear-gradient(90deg,#4C78A8 0%,#2E5A88 100%);'
        'padding:22px 28px;border-radius:14px;color:#fff;margin-bottom:10px;">'
        '<div style="font-size:26px;font-weight:800;letter-spacing:-.5px;">📈 마케팅 채널 효율성 분석</div>'
        '<div style="opacity:.92;margin-top:5px;font-size:15px;">'
        '채널별 유입 1건당 비용과 예산 집행률로 효율 채널을 진단합니다</div>'
        + chips + "</div>",
        unsafe_allow_html=True,
    )


def main():
    st.set_page_config(page_title="마케팅 채널 효율성 분석", layout="wide")
    render_banner()

    tab_marketing, tab_dashboard, tab_report = st.tabs(
        ["마케팅 채널 효율", "고객 이탈 분석", "이탈 개선 리포트"]
    )

    with tab_marketing:
        render_marketing_tab()

    with tab_dashboard:
        render_dashboard_tab()

    with tab_report:
        render_report_tab()


if __name__ == "__main__":
    main()
