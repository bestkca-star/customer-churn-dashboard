"""상담원별 고객 NPS 스코어카드.

주의: 이 차트는 직원 대상 eNPS가 아니다.
data_satisfaction.csv 의 nps(0~10)는 상담 건을 경험한 '고객'이 응답한 값이며,
consult_id 로 data_consultations.csv 의 agent_id 와 연결해 상담원 단위로 집계한 것이다.
직원 만족도 설문 데이터는 이 프로젝트에 존재하지 않는다.
"""

import csv
from pathlib import Path

import plotly.graph_objects as go


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# 응답 수가 너무 적은 상담원은 NPS가 크게 흔들리므로 제외
MIN_RESPONSES = 10


def read_csv_rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def calculate_nps(scores):
    """NPS = 추천고객(9~10) 비율 - 비추천고객(0~6) 비율, 단위는 포인트."""
    if not scores:
        return 0.0
    promoters = sum(1 for s in scores if s >= 9)
    detractors = sum(1 for s in scores if s <= 6)
    return round((promoters - detractors) / len(scores) * 100, 1)


def calculate_agent_nps():
    satisfaction = read_csv_rows(DATA_DIR / "data_satisfaction.csv")
    consultations = read_csv_rows(DATA_DIR / "data_consultations.csv")

    agent_by_consult = {row["consult_id"]: row.get("agent_id", "") for row in consultations}

    all_scores = []
    agent_scores = {}

    for row in satisfaction:
        raw = row.get("nps", "").strip()
        if not raw:
            continue
        score = int(raw)
        all_scores.append(score)

        agent_id = agent_by_consult.get(row.get("consult_id", ""))
        if agent_id:
            agent_scores.setdefault(agent_id, []).append(score)

    agents = []
    excluded = []
    for agent_id, scores in agent_scores.items():
        item = {
            "agent_id": agent_id,
            "response_count": len(scores),
            "nps": calculate_nps(scores),
        }
        if len(scores) >= MIN_RESPONSES:
            agents.append(item)
        else:
            excluded.append(item)

    agents.sort(key=lambda x: x["nps"], reverse=True)
    return calculate_nps(all_scores), len(all_scores), agents, excluded


if __name__ == "__main__":
    overall_nps, total_responses, agents, excluded = calculate_agent_nps()

    best = agents[0]
    median = agents[len(agents) // 2]
    worst = agents[-1]
    cards = [
        ("최고 상담원", best, 0.48, 0.65),
        ("중앙값 상담원", median, 0.66, 0.83),
        ("최저 상담원", worst, 0.84, 1.00),
    ]

    fig = go.Figure()

    # 큰 게이지: 전체 고객 NPS (-100 ~ 100, 마이너스 구간은 빨간 계열 배경)
    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=overall_nps,
        number={"suffix": "점", "font": {"size": 48}},
        title={
            "text": f"전체 고객 NPS<br><span style='font-size:13px;color:#666'>"
                    f"응답 {total_responses:,}건 · 상담원 {len(agents)}명</span>",
            "font": {"size": 20},
        },
        domain={"x": [0.02, 0.42], "y": [0.05, 0.92]},
        gauge={
            "axis": {
                "range": [-100, 100],
                "tickmode": "array",
                "tickvals": [-100, -50, 0, 50, 100],
                "tickfont": {"size": 12},
            },
            "bar": {"color": "#2F4F4F", "thickness": 0.28},
            "borderwidth": 1,
            "bordercolor": "#D9D9D9",
            "steps": [
                {"range": [-100, -50], "color": "#E45756"},
                {"range": [-50, 0], "color": "#F5B0AF"},
                {"range": [0, 50], "color": "#EDF3F8"},
                {"range": [50, 100], "color": "#BBD3E8"},
            ],
            "threshold": {
                "line": {"color": "#333333", "width": 3},
                "thickness": 0.85,
                "value": 0,
            },
        },
    ))

    # 작은 숫자 카드 3개: 전체 NPS 대비 델타 표시
    for label, agent, x0, x1 in cards:
        fig.add_trace(go.Indicator(
            mode="number+delta",
            value=agent["nps"],
            number={"suffix": "점", "font": {"size": 34}},
            delta={
                "reference": overall_nps,
                "valueformat": ".1f",
                "increasing": {"color": "#4C78A8"},
                "decreasing": {"color": "#E45756"},
                "font": {"size": 15},
            },
            title={
                "text": f"{label}<br><span style='font-size:12px;color:#666'>"
                        f"{agent['agent_id']} · {agent['response_count']}건</span>",
                "font": {"size": 16},
            },
            domain={"x": [x0, x1], "y": [0.30, 0.78]},
        ))

    fig.update_layout(
        template="plotly_white",
        title={
            "text": "상담원별 고객 NPS 스코어카드"
                    "<br><span style='font-size:12px;color:#888'>"
                    "※ 직원 대상 eNPS가 아니라, 상담을 경험한 고객이 응답한 NPS입니다</span>",
            "x": 0.02,
            "xanchor": "left",
        },
        font=dict(family="Malgun Gothic, Arial, sans-serif"),
        height=460,
        margin=dict(t=110, b=30, l=30, r=30),
    )

    print(f"전체 고객 NPS: {overall_nps}점 (응답 {total_responses:,}건)")
    for label, agent, _, _ in cards:
        print(f"  {label}: {agent['agent_id']} {agent['nps']}점 ({agent['response_count']}건)")
    if excluded:
        names = ", ".join(f"{a['agent_id']}({a['response_count']}건)" for a in excluded)
        print(f"응답 {MIN_RESPONSES}건 미만으로 제외한 상담원: {names}")

    fig.show()
