"""Benchmark several git refs of murky-tree against a baseline.

Each ref is checked out into its own git worktree under ``benchmarks/.worktrees``
with its own uv environment (built non-editable, so v2's Rust extension is a
release build). ``bench.py`` from *this* checkout is then run inside every
environment, so all refs are measured with identical benchmark code, and the
results are merged into a markdown table of timings and speedups.

Usage (stdlib only, any Python >= 3.10)::

    python3 benchmarks/compare.py                       # v1.2 and v2 vs 1.1.0
    python3 benchmarks/compare.py main v2 --baseline v1.2 --sizes 1000
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
REPO = BENCH_DIR.parent
WORKTREES = BENCH_DIR / ".worktrees"


def run(cmd: list[str], **kwargs) -> str:
    print("$ " + " ".join(str(c) for c in cmd), file=sys.stderr)
    return subprocess.run(
        cmd, check=True, text=True, stdout=subprocess.PIPE, **kwargs
    ).stdout.strip()


def git(*args: str, cwd: Path = REPO) -> str:
    return run(["git", "-C", str(cwd), *args])


def tool_env(worktree: Path) -> dict[str, str]:
    env = os.environ.copy()
    # Give each worktree its own venv, overriding any global uv setting.
    env["UV_PROJECT_ENVIRONMENT"] = str(worktree / ".venv")
    env.pop("VIRTUAL_ENV", None)
    cargo_bin = Path.home() / ".cargo" / "bin"
    if shutil.which("cargo", path=env.get("PATH")) is None and cargo_bin.is_dir():
        env["PATH"] = f"{cargo_bin}{os.pathsep}{env.get('PATH', '')}"
    return env


def prepare(ref: str, python: str) -> tuple[Path, str]:
    """Check out ``ref`` into a worktree and sync its environment."""
    sha = git("rev-parse", "--verify", f"{ref}^{{commit}}")
    worktree = WORKTREES / ref.replace("/", "_")
    if (worktree / ".git").exists():
        git("checkout", "--quiet", "--detach", sha, cwd=worktree)
    else:
        git("worktree", "prune")
        git("worktree", "add", "--quiet", "--detach", str(worktree), sha)

    run(
        [
            "uv", "sync", "--frozen", "--no-editable",
            "--reinstall-package", "murky-tree",
            "--python", python,
            "--project", str(worktree),
        ],
        env=tool_env(worktree),
    )  # fmt: skip
    return worktree, sha


def bench(ref: str, worktree: Path, bench_args: list[str]) -> dict:
    out = WORKTREES / f"{ref.replace('/', '_')}.json"
    python = worktree / ".venv" / ("Scripts" if os.name == "nt" else "bin") / "python"
    print(f"\n== benchmarking {ref} ==", file=sys.stderr)
    # Run from a neutral cwd so nothing but the installed package is importable.
    subprocess.run(
        [str(python), str(BENCH_DIR / "bench.py"), *bench_args, "--json", str(out)],
        check=True,
        cwd=WORKTREES,
        env=tool_env(worktree),
    )
    return json.loads(out.read_text())


def fmt_time(seconds: float) -> str:
    for unit, scale in (("s", 1), ("ms", 1e-3), ("µs", 1e-6)):
        if seconds >= scale:
            return f"{seconds / scale:.2f} {unit}"
    return f"{seconds / 1e-9:.0f} ns"


def fmt_speedup(base: float, new: float) -> str:
    ratio = base / new
    text = f"{ratio:.2f}×"
    return f"**{text}**" if ratio >= 1.1 else text


def render(baseline: str, refs: list[str], data: dict[str, dict], shas: dict) -> str:
    def key(r: dict) -> tuple[str, int]:
        return r["name"], r["size"]

    timings = {ref: {key(r): r["best"] for r in data[ref]["results"]} for ref in data}
    rows = list(timings[baseline])

    header = ["Benchmark", "N", f"`{baseline}`"]
    for ref in refs:
        header += [f"`{ref}`", f"vs `{baseline}`"]
    lines = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join(["---"] + ["--:"] * (len(header) - 1)) + "|",
    ]
    for name, size in rows:
        base = timings[baseline][(name, size)]
        cells = [name, f"{size:,}", fmt_time(base)]
        for ref in refs:
            new = timings[ref].get((name, size))
            cells += ["–", "–"] if new is None else [
                fmt_time(new), fmt_speedup(base, new)
            ]  # fmt: skip
        lines.append("| " + " | ".join(cells) + " |")

    meta = data[baseline]["meta"]
    refs_line = ", ".join(
        f"`{r}` ({shas[r][:7]}, murky-tree {data[r]['meta']['murky_tree_version']})"
        for r in [baseline, *refs]
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return "\n".join(
        [
            "# murky-tree benchmarks",
            "",
            f"- Date: {now}",
            f"- Refs: {refs_line}",
            f"- Python: {meta['implementation']} {meta['python']}",
            f"- Platform: {meta['platform']} ({platform.processor() or 'unknown cpu'})",
            "",
            "Times are the best per-call time over several repeats (lower is "
            "better). Speedup is baseline time / ref time; **bold** is ≥ 1.1× "
            "faster.",
            "",
            *lines,
            "",
        ]
    )


def check_roots(data: dict[str, dict], baseline: str) -> None:
    for ref, result in data.items():
        if result["roots"] != data[baseline]["roots"]:
            print(
                f"WARNING: {ref} produced different merkle roots than {baseline}",
                file=sys.stderr,
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("refs", nargs="*", default=["v1.2", "v2"])
    parser.add_argument("--baseline", default="1.1.0")
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="interpreter for every env (default: the one running this script)",
    )
    parser.add_argument("--output", type=Path, default=BENCH_DIR / "results.md")
    parser.add_argument(
        "--clean", action="store_true", help="remove the worktrees when done"
    )
    forwarded = parser.add_argument_group("forwarded to bench.py")
    forwarded.add_argument("--sizes", nargs="+")
    forwarded.add_argument("--multi")
    forwarded.add_argument("--repeat")
    forwarded.add_argument("--min-time")
    forwarded.add_argument("--filter")
    args = parser.parse_args()

    bench_args: list[str] = []
    for name in ("sizes", "multi", "repeat", "min_time", "filter"):
        value = getattr(args, name)
        if value is not None:
            flag = "--" + name.replace("_", "-")
            bench_args += [flag, *value] if isinstance(value, list) else [flag, value]

    refs = [r for r in args.refs if r != args.baseline]
    WORKTREES.mkdir(exist_ok=True)

    data: dict[str, dict] = {}
    shas: dict[str, str] = {}
    try:
        for ref in [args.baseline, *refs]:
            worktree, shas[ref] = prepare(ref, args.python)
            data[ref] = bench(ref, worktree, bench_args)
    finally:
        if args.clean:
            for ref in [args.baseline, *refs]:
                worktree = WORKTREES / ref.replace("/", "_")
                if worktree.exists():
                    git("worktree", "remove", "--force", str(worktree))

    check_roots(data, args.baseline)
    report = render(args.baseline, refs, data, shas)
    args.output.write_text(report)
    (args.output.with_suffix(".json")).write_text(
        json.dumps({"shas": shas, "data": data}, indent=2)
    )
    print("\n" + report)
    print(f"Wrote {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
