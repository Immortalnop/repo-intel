"""Command-line surface. One subcommand per health check.

repo-intel analyze .                 full report -> table
repo-intel analyze . -o r.json       export (fmt from extension: json/md/html/csv)
repo-intel health .                  health score
repo-intel hotspots . -n 15          bug-prone modules
repo-intel busfactor .               knowledge concentration
repo-intel drift .                   architectural coupling
repo-intel readiness .               release readiness
repo-intel predict .                 trend / regression risk
repo-intel authors .                 contribution breakdown
repo-intel flags .                   raised flags
repo-intel summary . --llm           narrative (Qwen if reachable, else rule-based)
repo-intel serve .                   launch API + GUI
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from .. import __version__
from .. import llm as llm_pkg
from ..config import Config
from ..logging_utils import configure_logging
from ..report import exporters
from ..report.builder import analyze

_C = sys.stdout.isatty()


def _c(t, code):
    return f"\033[{code}m{t}\033[0m" if _C else t


def bold(t):
    return _c(t, "1")


def red(t):
    return _c(t, "31")


def yel(t):
    return _c(t, "33")


def grn(t):
    return _c(t, "32")


def dim(t):
    return _c(t, "2")


LEVEL = {"high": red, "medium": yel, "info": grn, "low": dim}


def _get(args) -> dict:
    if getattr(args, "verbose", False):
        configure_logging("INFO")
    cfg = Config.resolve(getattr(args, "config", None), getattr(args, "repo", None))
    if getattr(args, "skip_merges", False):
        cfg = replace(cfg, skip_merges=True)
    since = None
    if getattr(args, "since_days", None):
        since = datetime.now(timezone.utc) - timedelta(days=args.since_days)
    return analyze(
        args.repo,
        since=since,
        branch=getattr(args, "branch", None),
        max_commits=getattr(args, "max_commits", None),
        top=getattr(args, "top", 20),
        use_cache=getattr(args, "cache", False),
        incremental=getattr(args, "incremental", False),
        jobs=getattr(args, "jobs", 1),
        timeout=getattr(args, "timeout", None),
        cfg=cfg,
    )


def _table(rows, cols, widths):
    print("  ".join(bold(c.ljust(w)) for c, w in zip(cols, widths)))
    print(dim("  ".join("-" * w for w in widths)))
    for r in rows:
        print("  ".join(str(v)[:w].ljust(w) for v, w in zip(r, widths)))


def _score(v):
    return (grn if v >= 70 else yel if v >= 45 else red)(str(v))


def _verdict(v):
    return {"READY": grn, "CAUTION": yel, "NOT READY": red}.get(v, str)(v)


def _print_flags(rep):
    for f in rep["flags"]:
        print(
            f"{LEVEL.get(f['level'], str)('['+f['level'].upper()+']'):<10} "
            f"{f['code']:<22} {f['message']}"
        )


def cmd_analyze(args):
    rep = _get(args)
    if args.output:
        fmt = args.format or args.output.rsplit(".", 1)[-1]
        exporters.export(rep, fmt, args.output)
        print(grn(f"Report ({fmt}) -> {args.output}"))
        if not args.show:
            return
    s, rr = rep["summary"], rep["release_readiness"]
    print(bold(f"\n=== {rep['repo']} ==="))
    print(f"Health score : {_score(s['health_score'])}/100")
    print(
        f"Commits {s['commits']} | Files {s['files']} | Authors {s['authors']} "
        f"| Bug-fix commits {s['bugfix_commits']} | Churn {s['total_churn']}"
    )
    print(f"Release      : {_verdict(rr['verdict'])} ({rr['score']}/100)")
    print(f"Trend        : {rep['prediction'].get('trend','n/a')}")
    print(bold("\nTop bug-prone modules:"))
    _table(
        [
            (h["path"], h["risk_score"], h["churn"], h["bugfixes"], h["authors"], h["bus_factor"])
            for h in rep["hotspots"][:10]
        ],
        ["FILE", "RISK", "CHURN", "FIXES", "AUTH", "BUS"],
        [46, 6, 7, 6, 5, 4],
    )
    print(bold("\nFlags:"))
    _print_flags(rep)


def cmd_health(args):
    s = _get(args)["summary"]
    print(
        f"{_score(s['health_score'])}/100  (commits {s['commits']}, files {s['files']}, "
        f"authors {s['authors']}, bug-fix commits {s['bugfix_commits']})"
    )


def cmd_hotspots(args):
    rep = _get(args)
    print(bold("Bug-prone modules (by risk score):"))
    _table(
        [
            (
                h["path"],
                h["risk_score"],
                h["churn"],
                h["bugfixes"],
                f"{h['bugfix_ratio']:.0%}",
                h["recency"],
            )
            for h in rep["hotspots"][: args.top]
        ],
        ["FILE", "RISK", "CHURN", "FIXES", "FIX%", "RECENCY"],
        [46, 6, 7, 6, 6, 8],
    )


def cmd_busfactor(args):
    rep = _get(args)
    print(bold("Knowledge concentration / bus-factor risk:"))
    if not rep["knowledge_silos"]:
        print(grn("No single-owner files detected."))
        return
    _table(
        [
            (
                s["path"],
                s["top_author"],
                f"{s['top_author_share']:.0%}",
                s["bus_factor"],
                s["commits"],
            )
            for s in rep["knowledge_silos"][: args.top]
        ],
        ["FILE", "OWNER", "SHARE", "BUS", "COMMITS"],
        [40, 20, 6, 4, 8],
    )


def cmd_drift(args):
    rep = _get(args)
    print(bold("Architectural drift (temporal coupling):"))
    if not rep["coupling"]:
        print(grn("No significant coupling detected."))
        return
    _table(
        [
            (
                c["file_a"],
                c["file_b"],
                c["shared_changes"],
                f"{c['confidence']:.0%}",
                "YES" if c["cross_module"] else "-",
            )
            for c in rep["coupling"][: args.top]
        ],
        ["FILE A", "FILE B", "CO-CHG", "CONF", "X-MOD"],
        [30, 30, 7, 6, 6],
    )


def cmd_readiness(args):
    rr = _get(args)["release_readiness"]
    print(
        f"Release readiness: {_verdict(rr['verdict'])}  {rr['score']}/100  "
        f"(last {rr['window_days']} days, {rr['commits_in_window']} commits)"
    )
    for r in rr.get("reasons", []):
        print(f"  - {r}")


def cmd_predict(args):
    p = _get(args)["prediction"]
    print(bold("Predictive risk (trend / regression):"))
    for k, v in p.items():
        print(f"  {k:<32} {v}")


def cmd_authors(args):
    rep = _get(args)
    print(bold("Author contribution:"))
    _table(
        [(a["author"], a["commits"], f"{a['share']:.0%}") for a in rep["authors"][: args.top]],
        ["AUTHOR", "COMMITS", "SHARE"],
        [30, 8, 6],
    )


def cmd_complexity(args):
    if getattr(args, "verbose", False):
        configure_logging("INFO")
    cfg = Config.resolve(getattr(args, "config", None), getattr(args, "repo", None))
    rep = analyze(args.repo, top=getattr(args, "top", 20), complexity_trend=True, cfg=cfg)
    if not rep["summary"]["complexity_available"]:
        print(red("Complexity unavailable — install lizard: pip install '.[complexity]'"))
        return
    print(bold("Cyclomatic complexity — current hotspots:"))
    rows = [
        (
            h["path"],
            h.get("complexity", "—"),
            h.get("complexity_max", "—"),
            h.get("complexity_language", "—"),
        )
        for h in rep["hotspots"][: args.top]
        if h.get("complexity") is not None
    ]
    _table(
        rows or [("(no analyzable source files)", "", "", "")],
        ["FILE", "AVG", "MAX", "LANG"],
        [46, 6, 6, 12],
    )
    trend = rep.get("complexity_trend", [])
    if trend:
        print(bold("\nComplexity trend over history:"))
        _table(
            [(p["date"][:10], p["avg_complexity"], p["functions"], p["files"]) for p in trend],
            ["DATE", "AVG CX", "FUNCS", "FILES"],
            [12, 8, 7, 7],
        )


def cmd_departure(args):
    rep = _get(args)
    print(bold("Author departure risk (truck factor):"))
    if not rep["departure_risk"]:
        print(grn("No single-author knowledge silos."))
        return
    _table(
        [
            (d["author"], d["owned_files"], f"{d['codebase_share']:.0%}", ", ".join(d["files"][:3]))
            for d in rep["departure_risk"][: args.top]
        ],
        ["AUTHOR", "OWNS", "CODEBASE", "EXAMPLE FILES"],
        [24, 6, 8, 46],
    )


def cmd_flags(args):
    _print_flags(_get(args))


def cmd_summary(args):
    rep = _get(args)
    provider = llm_pkg.get_provider("auto" if args.llm else "none")
    res = provider.summarize(rep)
    tag = res["source"] + (f" ({res['model']})" if res.get("model") else "")
    print(dim(f"[narrative source: {tag}]"))
    print(res["text"])


def cmd_serve(args):
    from ..api.server import serve

    serve(
        args.repo,
        host=args.host,
        port=args.port,
        since_days=getattr(args, "since_days", None),
        max_commits=getattr(args, "max_commits", None),
        fresh=getattr(args, "fresh", False),
        cx_trend=getattr(args, "cx_trend", False),
    )


def cmd_store(args):
    from ..storage import DEFAULT_STORE, purge

    if args.action == "list":
        rows = DEFAULT_STORE.list()
        if not rows:
            print(grn("No stored projects."))
            return
        _table(
            [(m.repo, m.n_commits, m.n_files, m.health, m.head or "-") for m in rows],
            ["REPO", "COMMITS", "FILES", "HEALTH", "HEAD"],
            [48, 8, 6, 7, 12],
        )
    elif args.action == "clear":
        if args.all:
            n = DEFAULT_STORE.clear_all()
            from ..extract import cache

            cache.clear_all()
            print(grn(f"Cleared all stored data ({n} project(s))."))
        elif args.repo:
            res = purge(args.repo)
            print(
                grn(
                    f"Cleared {res['repo']}: report_removed={res['report_removed']}, "
                    f"cache_files_removed={res['cache_files_removed']}"
                )
            )
        else:
            print(red("store clear needs a repo path or --all"), file=sys.stderr)
            sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="repo-intel", description="Git Repository Intelligence")
    p.add_argument("--version", action="version", version=f"repo-intel {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, top_default=20):
        sp.add_argument("repo", nargs="?", default=".")
        sp.add_argument("--branch")
        sp.add_argument("--since-days", type=int)
        sp.add_argument("--max-commits", type=int)
        sp.add_argument("-n", "--top", type=int, default=top_default)
        sp.add_argument("--cache", action="store_true", help="use sqlite/parquet cache")
        sp.add_argument(
            "--incremental", action="store_true", help="extend cached history with only new commits"
        )
        sp.add_argument("--jobs", type=int, default=1, help="parallel mining workers")
        sp.add_argument("--timeout", type=float, help="abort mining after N seconds")
        sp.add_argument("--skip-merges", action="store_true", help="ignore merge commits")
        sp.add_argument("--config", help="path to a repo-intel.toml config file")
        sp.add_argument("-v", "--verbose", action="store_true", help="INFO logging")

    a = sub.add_parser("analyze", help="full analysis")
    common(a)
    a.add_argument("-o", "--output", help="export file (json/md/html/csv by extension)")
    a.add_argument("--format", help="override export format")
    a.add_argument("--show", action="store_true", help="also print overview after export")
    a.set_defaults(func=cmd_analyze)

    for name, fn, h in [
        ("health", cmd_health, "overall health score"),
        ("hotspots", cmd_hotspots, "bug-prone modules"),
        ("busfactor", cmd_busfactor, "knowledge concentration"),
        ("drift", cmd_drift, "architectural coupling"),
        ("readiness", cmd_readiness, "release readiness"),
        ("predict", cmd_predict, "trend / regression risk"),
        ("complexity", cmd_complexity, "cyclomatic complexity + history trend"),
        ("departure", cmd_departure, "author departure / truck-factor risk"),
        ("authors", cmd_authors, "author contribution"),
        ("flags", cmd_flags, "raised risk flags"),
    ]:
        sp = sub.add_parser(name, help=h)
        common(sp)
        sp.set_defaults(func=fn)

    sm = sub.add_parser("summary", help="natural-language briefing")
    common(sm)
    sm.add_argument("--llm", action="store_true", help="use local Qwen (else rule-based)")
    sm.set_defaults(func=cmd_summary)

    sv = sub.add_parser("serve", help="launch API + GUI")
    sv.add_argument("repo", nargs="?", default=".")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    sv.add_argument("--since-days", type=int)
    sv.add_argument("--max-commits", type=int)
    sv.add_argument("--fresh", action="store_true", help="ignore stored report, re-mine")
    sv.add_argument("--cx-trend", action="store_true", help="compute complexity history trend")
    sv.set_defaults(func=cmd_serve)

    st = sub.add_parser("store", help="manage persisted reports")
    st.add_argument("action", choices=["list", "clear"])
    st.add_argument("repo", nargs="?", help="repo path (for clear)")
    st.add_argument("--all", action="store_true", help="clear every stored project")
    st.add_argument("-n", "--top", type=int, default=50)
    st.set_defaults(func=cmd_store)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:
        print(red(f"error: {exc}"), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
