"""Performance benchmark for repo-intel mining.

Measures wall-clock time and peak memory (tracemalloc + RSS) for serial vs
parallel mining across repository sizes. Generates synthetic repos with
genrepo.py when a size is not already present.

Usage:
    python benchmarks/bench.py 1000 5000 20000 [--jobs 4] [--repo-dir /tmp/ri_bench]
"""

from __future__ import annotations

import argparse
import gc
import time
import tracemalloc
from pathlib import Path

from repo_intel.extract import driller, mine


def _rss_mb() -> float:
    try:
        import resource
        import sys

        val = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # ru_maxrss is KB on Linux, bytes on macOS
        return val / (1024 * 1024) if sys.platform == "darwin" else val / 1024
    except Exception:
        return 0.0


def _time_it(fn) -> tuple[float, float, object]:
    gc.collect()
    tracemalloc.start()
    t0 = time.perf_counter()
    result = fn()
    dt = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return dt, peak / 1_048_576, result


def ensure_repo(repo_dir: Path, n: int) -> str:
    path = repo_dir / f"repo_{n}"
    if not (path / ".git").exists():
        from benchmarks.genrepo import gen

        gen(str(path), n)
    return str(path)


def bench(sizes: list[int], jobs: int, repo_dir: Path) -> list[dict]:
    rows = []
    for n in sizes:
        repo = ensure_repo(repo_dir, n)
        commits = int(
            __import__("subprocess")
            .run(["git", "-C", repo, "rev-list", "--count", "HEAD"], capture_output=True, text=True)
            .stdout.strip()
        )
        t_ser, mem_ser, hist = _time_it(lambda r=repo: driller.drill(r))
        t_par, _mem_par, _ = _time_it(lambda r=repo, j=jobs: mine.drill_parallel(r, jobs=j))
        rows.append(
            {
                "commits": commits,
                "files": len(hist.files),
                "serial_s": round(t_ser, 2),
                "serial_commits_per_s": round(commits / t_ser, 0),
                "serial_peak_mb": round(mem_ser, 1),
                f"parallel_s(j={jobs})": round(t_par, 2),
                "speedup": round(t_ser / t_par, 2) if t_par else None,
                "rss_mb": round(_rss_mb(), 1),
            }
        )
        print(rows[-1])
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sizes", nargs="+", type=int)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--repo-dir", default="/tmp/ri_bench")
    args = ap.parse_args()
    repo_dir = Path(args.repo_dir)
    repo_dir.mkdir(parents=True, exist_ok=True)
    rows = bench(sorted(args.sizes), args.jobs, repo_dir)
    print(
        "\n| commits | files | serial s | commits/s | serial peak MB | "
        f"parallel s (j={args.jobs}) | speedup | RSS MB |"
    )
    print("|--:|--:|--:|--:|--:|--:|--:|--:|")
    for r in rows:
        print(
            f"| {r['commits']:,} | {r['files']} | {r['serial_s']} | "
            f"{int(r['serial_commits_per_s']):,} | {r['serial_peak_mb']} | "
            f"{r[f'parallel_s(j={args.jobs})']} | {r['speedup']}x | {r['rss_mb']} |"
        )


if __name__ == "__main__":
    main()
