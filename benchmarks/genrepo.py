"""Generate a large synthetic Git repo fast, via `git fast-import`.

Usage: python benchmarks/genrepo.py <path> <n_commits> [n_files] [n_authors]
Creates realistic-ish history: rotating files, some bug-fix messages, multiple
authors. Used for performance benchmarking (see bench.py).
"""

import subprocess
import sys
from pathlib import Path


def gen(path: str, n_commits: int, n_files: int = 200, n_authors: int = 10) -> None:
    root = Path(path)
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    proc = subprocess.Popen(["git", "fast-import", "--quiet"], cwd=root, stdin=subprocess.PIPE)
    out = proc.stdin
    base = 1_600_000_000

    def w(s: bytes) -> None:
        out.write(s)

    for i in range(1, n_commits + 1):
        author = f"Dev{i % n_authors} <dev{i % n_authors}@x.com>"
        msg = f"change {i}" + (" fix crash bug" if i % 3 == 0 else "")
        mb = msg.encode()
        w(b"commit refs/heads/main\n")
        w(f"committer {author} {base + i * 60} +0000\n".encode())
        w(f"data {len(mb)}\n".encode())
        w(mb + b"\n")
        # touch 1-3 files per commit
        for k in range(1 + (i % 3)):
            fidx = (i + k) % n_files
            content = (
                f"def func_{fidx}(x):\n"
                f"    if x > {i % 7}:\n"
                f"        return {i}\n"
                f"    elif x < 0:\n"
                f"        return -{k}\n"
                f"    return 0\n"
            ).encode()
            w(f"M 100644 inline src/mod_{fidx}.py\n".encode())
            w(f"data {len(content)}\n".encode())
            w(content + b"\n")
    out.close()
    proc.wait()
    subprocess.run(["git", "reset", "--hard", "-q", "main"], cwd=root, check=True)


if __name__ == "__main__":
    gen(
        sys.argv[1],
        int(sys.argv[2]),
        int(sys.argv[3]) if len(sys.argv) > 3 else 200,
        int(sys.argv[4]) if len(sys.argv) > 4 else 10,
    )
    n = subprocess.run(
        ["git", "-C", sys.argv[1], "rev-list", "--count", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    print(f"generated {n} commits at {sys.argv[1]}")
