"""상담원 업무부하와 CSAT 평균의 관계 산점도.

주의: '초과근무 시간(overtime_hours_avg)' 데이터는 이 프로젝트에 존재하지 않는다.
data/ 아래에는 고객 관점 CSV 5개만 있고, 직원 근태 테이블이 없다.

그래서 x축은 기존 데이터로 실제 계산 가능한 '업무부하'(상담원별 총 상담시간)를
번아웃 대리지표로 사용한다. 실제 초과근무 데이터가 생기면
data/data_agent_overtime.csv 에 (agent_id, overtime_hours_avg) 컬럼으로 넣어두기만 하면
아래 load_overtime() 이 자동으로 그 값을 x축으로 쓴다.

필요 패키지: plotly, pandas, statsmodels (trendline="ols" 에 statsmodels 필요)
"""

import csv
from pathlib import Path

import pandas as pd
import plotly.express as px


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

OVERTIME_CSV = DATA_DIR / "data_agent_overtime.csv"

# CSAT 응답이 적은 상담원은 평균이 크게 흔들리므로 제외
MIN_RESPONSES = 10


def read_csv_rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_overtime():
    """실제 초과근무 데이터가 있으면 {agent_id: overtime_hours_avg} 로 반환, 없으면 None."""
    if not OVERTIME_CSV.exists():
        return None
    rows = read_csv_rows(OVERTIME_CSV)
    return {row["agent_id"]: float(row["overtime_hours_avg"]) for row in rows}


def calculate_agent_metrics():
    """상담원별 CSAT 평균과 업무부하(총 상담시간)를 재계산한다."""
    consultations = read_csv_rows(DATA_DIR / "data_consultations.csv")
    satisfaction = read_csv_rows(DATA_DIR / "data_satisfaction.csv")

    agent_by_consult = {row["consult_id"]: row.get("agent_id", "") for row in consultations}

    workload = {}
    for row in consultations:
        agent_id = row.get("agent_id", "")
        if not agent_id:
            continue
        stats = workload.setdefault(agent_id, {"consult_count": 0, "total_min": 0})
        stats["consult_count"] += 1
        stats["total_min"] += int(row.get("duration_min") or 0)

    csat_scores = {}
    for row in satisfaction:
        raw = row.get("csat", "").strip()
        if not raw:
            continue
        agent_id = agent_by_consult.get(row.get("consult_id", ""))
        if agent_id:
            csat_scores.setdefault(agent_id, []).append(int(raw))

    overtime = load_overtime()

    agents = []
    excluded = []
    for agent_id, scores in csat_scores.items():
        stats = workload.get(agent_id, {"consult_count": 0, "total_min": 0})
        item = {
            "agent_id": agent_id,
            "업무부하_총상담시간": round(stats["total_min"] / 60, 1),
            "CSAT_평균": round(sum(scores) / len(scores), 2),
            "상담건수": stats["consult_count"],
            "응답수": len(scores),
        }
        if overtime is not None:
            item["overtime_hours_avg"] = overtime.get(agent_id)

        if len(scores) >= MIN_RESPONSES:
            agents.append(item)
        else:
            excluded.append(item)

    agents.sort(key=lambda x: x["agent_id"])
    return agents, excluded, overtime is not None


def pearson_r(xs, ys):
    n = len(xs)
    if n < 2:
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return 0.0
    return cov / (var_x * var_y) ** 0.5


if __name__ == "__main__":
    agents, excluded, has_overtime = calculate_agent_metrics()

    if has_overtime:
        x_col = "overtime_hours_avg"
        x_label = "평균 초과근무 시간 (시간)"
        subtitle = "실제 초과근무 데이터 기준"
    else:
        x_col = "업무부하_총상담시간"
        x_label = "업무부하 · 총 상담시간 (시간)"
        subtitle = "※ 초과근무 데이터가 없어 '총 상담시간'을 번아웃 대리지표로 사용"

    df = pd.DataFrame(agents)
    r = pearson_r(df[x_col].tolist(), df["CSAT_평균"].tolist())

    fig = px.scatter(
        df,
        x=x_col,
        y="CSAT_평균",
        trendline="ols",
        trendline_color_override="#E45756",
        hover_name="agent_id",
        hover_data={
            x_col: ":.1f",
            "CSAT_평균": ":.2f",
            "상담건수": True,
            "응답수": True,
        },
        labels={
            x_col: x_label,
            "CSAT_평균": "CSAT 평균 (1~5점)",
            "상담건수": "상담 건수",
            "응답수": "CSAT 응답 수",
        },
        title=f"업무부하와 CSAT 평균의 관계<br>"
              f"<span style='font-size:12px;color:#888'>{subtitle}</span>",
    )

    fig.update_traces(
        marker=dict(size=13, color="#4C78A8", line=dict(width=1, color="white")),
        selector=dict(mode="markers"),
    )

    # 오른쪽 위에 상관계수 표시
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.99, y=0.98,
        xanchor="right", yanchor="top",
        text=f"<b>r = {r:.2f}</b>",
        showarrow=False,
        font=dict(size=18, color="#E45756"),
        bgcolor="rgba(255,255,255,0.85)",
        bordercolor="#E45756",
        borderwidth=1,
        borderpad=6,
    )

    fig.update_layout(
        template="plotly_white",
        font=dict(family="Malgun Gothic, Arial, sans-serif"),
        xaxis_title=x_label,
        yaxis_title="CSAT 평균 (1~5점)",
        margin=dict(t=90),
    )

    print(f"상담원 {len(df)}명 · 상관계수 r = {r:.2f}  (x축: {x_col})")
    print(df[["agent_id", x_col, "CSAT_평균", "상담건수"]].to_string(index=False))
    if excluded:
        names = ", ".join(f"{a['agent_id']}({a['응답수']}건)" for a in excluded)
        print(f"CSAT 응답 {MIN_RESPONSES}건 미만으로 제외: {names}")

    fig.show()
