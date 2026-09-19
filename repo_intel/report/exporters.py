"""Export a report to json / md / html / csv."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path


def to_json(report: dict, path: str | None = None) -> str:
    s = json.dumps(report, indent=2, default=str)
    if path:
        Path(path).write_text(s)
    return s


def to_markdown(report: dict, path: str | None = None) -> str:
    s = report["summary"]
    rr = report["release_readiness"]
    L = [
        f"# Repository Intelligence — {report['repo']}",
        "",
        f"_Generated {report['generated_at']}_",
        "",
        f"**Health score:** {s['health_score']}/100  ",
        f"**Release readiness:** {rr['verdict']} ({rr['score']}/100)  ",
        f"**Commits:** {s['commits']} · **Files:** {s['files']} · "
        f"**Authors:** {s['authors']} · **Bug-fix commits:** {s['bugfix_commits']}",
        "",
        "## Flags",
        "",
    ]
    for f in report["flags"]:
        L.append(f"- **[{f['level'].upper()}] {f['code']}** — {f['message']}")
    L += [
        "",
        "## Bug-prone modules",
        "",
        "| File | Risk | Churn | Fixes | Authors | Bus |",
        "|---|---|---|---|---|---|",
    ]
    for h in report["hotspots"][:15]:
        L.append(
            f"| {h['path']} | {h['risk_score']} | {h['churn']} | "
            f"{h['bugfixes']} | {h['authors']} | {h['bus_factor']} |"
        )
    L += [
        "",
        "## Knowledge silos",
        "",
        "| File | Owner | Share | Bus factor |",
        "|---|---|---|---|",
    ]
    for x in report["knowledge_silos"][:15]:
        L.append(
            f"| {x['path']} | {x['top_author']} | "
            f"{x['top_author_share']:.0%} | {x['bus_factor']} |"
        )
    if report.get("prediction", {}).get("trend"):
        p = report["prediction"]
        L += ["", "## Predicted trend", "", f"- {p['trend']} — {p.get('note','')}"]
    out = "\n".join(L)
    if path:
        Path(path).write_text(out)
    return out


def to_csv(report: dict, path: str | None = None) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "path",
            "commits",
            "churn",
            "bugfixes",
            "bugfix_ratio",
            "authors",
            "top_author",
            "top_author_share",
            "bus_factor",
            "risk_score",
            "recency",
        ]
    )
    for r in report["all_files"]:
        w.writerow(
            [
                r["path"],
                r["commits"],
                r["churn"],
                r["bugfixes"],
                r["bugfix_ratio"],
                r["authors"],
                r["top_author"],
                r["top_author_share"],
                r["bus_factor"],
                r["risk_score"],
                r["recency"],
            ]
        )
    out = buf.getvalue()
    if path:
        Path(path).write_text(out)
    return out


def to_html(report: dict, path: str | None = None) -> str:
    """Self-contained static HTML report with embedded Plotly figures."""
    from . import charts

    figs = charts.all_figures(report)
    body = charts.figures_to_divs(figs)
    s = report["summary"]
    rr = report["release_readiness"]
    flags = "".join(
        f"<div class='flag {f['level']}'><b>{f['code']}</b> {f['message']}</div>"
        for f in report["flags"]
    )
    html = f"""<!doctype html><html><head><meta charset='utf-8'>
<title>Repo Intelligence — {report['repo']}</title>
<style>body{{font:14px system-ui;margin:24px;background:#0f1420;color:#e8edf5}}
.kpi{{display:inline-block;background:#171d2b;border:1px solid #273246;border-radius:10px;
padding:12px 18px;margin:6px}} .flag{{padding:6px 0}} .high{{color:#ff5d5d}}
.medium{{color:#ffb454}} .info{{color:#39d98a}} h1{{font-size:20px}}</style></head>
<body><h1>Repository Intelligence — {report['repo']}</h1>
<div class='kpi'>Health {s['health_score']}/100</div>
<div class='kpi'>Release {rr['verdict']} ({rr['score']})</div>
<div class='kpi'>Commits {s['commits']}</div>
<div class='kpi'>Files {s['files']}</div>
<div class='kpi'>Authors {s['authors']}</div>
<h2>Flags</h2>{flags}{body}</body></html>"""
    if path:
        Path(path).write_text(html)
    return html


EXPORTERS = {"json": to_json, "md": to_markdown, "html": to_html, "csv": to_csv}


def export(report: dict, fmt: str, path: str) -> str:
    fmt = fmt.lower()
    if fmt not in EXPORTERS:
        raise ValueError(f"unknown format: {fmt} (choose {list(EXPORTERS)})")
    return EXPORTERS[fmt](report, path)
