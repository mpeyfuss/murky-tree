# Benchmarks

Compare the performance of murky-tree across git refs.

```bash
python3 benchmarks/compare.py                    # v1.2 and v2 vs 1.1.0
python3 benchmarks/compare.py main --baseline v2 # any refs vs any baseline
python3 benchmarks/compare.py --sizes 1000 --filter Standard --repeat 3
```

`compare.py` needs only the stdlib, plus `uv` and `git` (and a Rust toolchain
for refs with the native backend, such as `v2`). For each ref it:

1. checks the ref out into a detached worktree at `benchmarks/.worktrees/<ref>`,
2. runs `uv sync --frozen --no-editable` there, building the package fresh
   into its own `.venv` with the same Python for every ref,
3. runs this checkout's `bench.py` in that environment, so every ref is
   measured with the same benchmark code.

The results are written to `benchmarks/results.md` (a markdown table of timings
and speedups against the baseline) and `benchmarks/results.json` (raw data).
The worktrees are kept between runs so later runs are faster; pass `--clean`
to remove them.

## Options

| Flag | Default | Meaning |
| --- | --- | --- |
| `refs` | `v1.2 v2` | refs to compare against the baseline |
| `--baseline` | `1.1.0` | ref that every speedup is measured against |
| `--python` | current interpreter | interpreter used for every environment |
| `--sizes` | `100 1000 10000` | numbers of leaves |
| `--multi` | `32` | leaves per multiproof |
| `--repeat` | `5` | timed repeats per benchmark (the best one is reported) |
| `--min-time` | `0.2` | minimum seconds per repeat |
| `--filter` | | only run benchmarks whose name contains this text |
| `--output` | `benchmarks/results.md` | report path (`.json` alongside) |
| `--clean` | off | remove the worktrees when done |

`bench.py` can also be run directly in any environment that has murky-tree
installed, e.g. `uv run python benchmarks/bench.py --sizes 1000`.

## What is measured

Each benchmark builds a deterministic dataset (`address, uint256` values for
`StandardMerkleTree`, random `bytes32` leaves for `SimpleMerkleTree`) and times
the public API only, so it runs on every version: `of`, `get_proof` (by index
and by value), `verify`, `verify_leaf`, `get_multi_proof`,
`verify_multi_proof`, `validate`, `to_json` and `from_json`. Single-proof
benchmarks cycle through 64 different leaves. `compare.py` warns if any ref
produces a different Merkle root than the baseline.
