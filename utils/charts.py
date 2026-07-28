import plotly.graph_objects as go


def create_score_chart(score):
    color = "#ef4444"

    if score >= 80:
        color = "#22c55e"
    elif score >= 60:
        color = "#f59e0b"

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            title={"text": "ATS Match Score"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": color},
                "steps": [
                    {"range": [0, 60], "color": "#fee2e2"},
                    {"range": [60, 80], "color": "#fef3c7"},
                    {"range": [80, 100], "color": "#dcfce7"},
                ],
            },
        )
    )

    fig.update_layout(height=350)

    return fig