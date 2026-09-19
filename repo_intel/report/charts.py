"""Plotly figure builders for the report (used by HTML export and the GUI)."""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

DARK = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#9aa7bd", size=11),
    margin=dict(t=30, r=12, b=36, l=48),
    xaxis=dict(gridcolor="#273246"),
    yaxis=dict(gridcolor="#273246"),
)


def RISK(v):
    return "#ff5d5d" if v >= 60 else "#ffb454" if v >= 40 else "#4f8cff"


def activity_figure(report: dict) -> go.Figure:
    act = report["commit_activity"]
    x = [a["month"] for a in act]
    fig = go.Figure()
    fig.add_scatter(
        x=x,
        y=[a["commits"] for a in act],
        mode="lines+markers",
        name="commits",
        line=dict(color="#4f8cff"),
    )
    fig.add_scatter(
        x=x,
        y=[a["bugfixes"] for a in act],
        mode="lines+markers",
        name="bug-fixes",
        line=dict(color="#ff5d5d"),
    )
    fig.update_layout(title="Commit activity (per month)", **DARK)
    return fig


def risk_figure(report: dict) -> go.Figure:
    h = list(reversed(report["hotspots"][:12]))
    fig = go.Figure(
        go.Bar(
            orientation="h",
            x=[d["risk_score"] for d in h],
            y=[d["path"].split("/")[-1] for d in h],
            marker_color=[RISK(d["risk_score"]) for d in h],
            text=[d["risk_score"] for d in h],
            textposition="auto",
        )
    )
    fig.update_layout(title="Top bug-prone modules (risk)", **DARK)
    fig.update_xaxes(range=[0, 100], type="linear")
    fig.update_yaxes(type="category", automargin=True)
    return fig


def authors_figure(report: dict) -> go.Figure:
    a = report["authors"][:8]
    fig = go.Figure(
        go.Pie(
            labels=[x["author"] for x in a],
            values=[x["commits"] for x in a],
            hole=0.55,
            textinfo="label+percent",
            marker=dict(
                colors=[
                    "#4f8cff",
                    "#39d98a",
                    "#ffb454",
                    "#ff5d5d",
                    "#a78bfa",
                    "#22d3ee",
                    "#f472b6",
                    "#94a3b8",
                ]
            ),
        )
    )
    fig.update_layout(title="Author contribution", showlegend=False, **DARK)
    return fig


def scatter_figure(report: dict) -> go.Figure:
    f = report["all_files"]
    fig = go.Figure(
        go.Scatter(
            x=[d["churn"] for d in f],
            y=[d["bugfixes"] for d in f],
            mode="markers",
            text=[d["path"] for d in f],
            marker=dict(
                size=[6 + d["risk_score"] / 6 for d in f],
                color=[d["risk_score"] for d in f],
                colorscale=[[0, "#4f8cff"], [0.5, "#ffb454"], [1, "#ff5d5d"]],
                showscale=False,
                opacity=0.8,
            ),
        )
    )
    fig.update_layout(title="Churn vs bug-fixes", **DARK)
    fig.update_xaxes(title="churn")
    fig.update_yaxes(title="bug-fixes")
    return fig


def all_figures(report: dict) -> dict[str, go.Figure]:
    return {
        "activity": activity_figure(report),
        "risk": risk_figure(report),
        "authors": authors_figure(report),
        "scatter": scatter_figure(report),
    }


def figures_to_divs(figs: dict[str, go.Figure]) -> str:
    """Embed figures as HTML divs; Plotly.js is inlined once (offline-safe)."""
    parts: list[str] = []
    first = True
    for fig in figs.values():
        parts.append(
            pio.to_html(
                fig,
                full_html=False,
                include_plotlyjs=(True if first else False),
                config={"displayModeBar": False},
            )
        )
        first = False
    return "<div style='margin-top:20px'>" + "".join(parts) + "</div>"
