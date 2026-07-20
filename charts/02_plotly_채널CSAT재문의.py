import csv
from pathlib import Path

import plotly.graph_objects as go


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def read_csv_rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def calculate_channel_metrics():
    consultations = read_csv_rows(DATA_DIR / "data_consultations.csv")
    satisfactions = read_csv_rows(DATA_DIR / "data_satisfaction.csv")

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
    return result


if __name__ == "__main__":
    data = calculate_channel_metrics()

    channels = [row["channel"] for row in data]
    csat_avg = [row["csat_avg"] for row in data]
    recontact_rates = [row["recontact_rate"] for row in data]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=channels,
        y=csat_avg,
        name="CSAT 평균",
        yaxis="y",
        marker_color="#4C78A8",
        hovertemplate="채널: %{x}<br>CSAT 평균: %{y:.2f}<extra></extra>",
    ))

    fig.add_trace(go.Scatter(
        x=channels,
        y=recontact_rates,
        mode="lines+markers",
        name="재문의율 (%)",
        yaxis="y2",
        line=dict(color="#E45756", width=3),
        marker=dict(color="#E45756", size=8),
        hovertemplate="채널: %{x}<br>재문의율: %{y:.2f}%<extra></extra>",
    ))

    fig.update_layout(
        title="채널별 CSAT 평균과 재문의율",
        xaxis_title="채널",
        yaxis_title="CSAT 평균",
        yaxis2=dict(title="재문의율 (%)", overlaying="y", side="right"),
        template="plotly_white",
        barmode="group",
        legend=dict(x=0.01, y=0.99),
        font=dict(family="Malgun Gothic, Arial, sans-serif"),
        hovermode="x unified",
    )

    fig.update_traces(
        hoverinfo="x+y",
        hovertemplate="채널: %{x}<br>CSAT 평균: %{y:.2f}<extra></extra>",
        selector=dict(type="bar")
    )
    fig.update_traces(
        hovertemplate="채널: %{x}<br>재문의율: %{y:.2f}%<extra></extra>",
        selector=dict(type="scatter")
    )

    fig.show()
