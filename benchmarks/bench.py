"""Micro-benchmarks for the public ``murky_tree`` API.

This script runs *inside* the environment of the version under test (see
``compare.py``), so it must only use the stdlib and API that exists in every
version being compared. Results are written as JSON to stdout or ``--json``.
"""

import argparse
import json
import platform
import random
import statistics
import sys
import timeit
from collections.abc import Callable
from importlib.metadata import version
from itertools import cycle

import murky_tree
from murky_tree import SimpleMerkleTree, StandardMerkleTree

ENCODING = ["address", "uint256"]
SEED = 1337
# Number of distinct leaves the per-call benchmarks cycle through.
SAMPLE = 64


def make_values(n: int) -> list[list]:
    rng = random.Random(SEED)
    return [
        ["0x" + rng.randbytes(20).hex(), rng.randrange(1, 10**24)] for _ in range(n)
    ]


def make_hashes(n: int) -> list[bytes]:
    rng = random.Random(SEED)
    return [rng.randbytes(32) for _ in range(n)]


def cycler(items: list) -> Callable:
    return cycle(items).__next__


def build_cases(n: int, multi: int) -> dict[str, Callable[[], object]]:
    """Return ``{name: zero-arg callable}``; each call is one timed operation."""
    rng = random.Random(SEED)
    values = make_values(n)
    hashes = make_hashes(n)

    std = StandardMerkleTree.of(values, ENCODING)
    simple = SimpleMerkleTree.of(hashes)
    std_json = std.to_json()

    sample = rng.sample(range(n), min(SAMPLE, n))
    std_proofs = [(values[i], std.get_proof(i)) for i in sample]
    simple_proofs = [(hashes[i], simple.get_proof(i)) for i in sample]
    next_index = cycler(sample)
    next_value = cycler([values[i] for i in sample])
    next_std_proof = cycler(std_proofs)
    next_simple_proof = cycler(simple_proofs)

    multi_indices = rng.sample(range(n), min(multi, n))
    k = len(multi_indices)
    std_multi = std.get_multi_proof(multi_indices)
    simple_multi = simple.get_multi_proof(multi_indices)

    def std_verify():
        value, proof = next_std_proof()
        return StandardMerkleTree.verify(std.root, ENCODING, value, proof)

    def std_verify_leaf():
        value, proof = next_std_proof()
        return std.verify_leaf(value, proof)

    def simple_verify():
        leaf, proof = next_simple_proof()
        return SimpleMerkleTree.verify(simple.root, leaf, proof)

    return {
        "Standard.of": lambda: StandardMerkleTree.of(values, ENCODING),
        "Standard.get_proof(index)": lambda: std.get_proof(next_index()),
        "Standard.get_proof(value)": lambda: std.get_proof(next_value()),
        "Standard.verify": std_verify,
        "Standard.verify_leaf": std_verify_leaf,
        f"Standard.get_multi_proof({k})": lambda: std.get_multi_proof(multi_indices),
        f"Standard.verify_multi_proof({k})": lambda: (
            StandardMerkleTree.verify_multi_proof(std.root, ENCODING, std_multi)
        ),
        "Standard.validate": std.validate,
        "Standard.to_json": std.to_json,
        "Standard.from_json": lambda: StandardMerkleTree.from_json(std_json),
        "Simple.of": lambda: SimpleMerkleTree.of(hashes),
        "Simple.get_proof(index)": lambda: simple.get_proof(next_index()),
        "Simple.verify": simple_verify,
        f"Simple.get_multi_proof({k})": lambda: simple.get_multi_proof(multi_indices),
        f"Simple.verify_multi_proof({k})": lambda: SimpleMerkleTree.verify_multi_proof(
            simple.root, simple_multi
        ),
        "Simple.validate": simple.validate,
    }


def time_case(fn: Callable[[], object], repeat: int, min_time: float) -> dict:
    timer = timeit.Timer(fn)
    # Calibrate the loop count so each repeat takes at least ``min_time``.
    number = 1
    while True:
        elapsed = timer.timeit(number)
        if elapsed >= min_time:
            break
        number = max(number * 2, int(number * min_time / max(elapsed, 1e-9)))
    runs = [t / number for t in timer.repeat(repeat=repeat, number=number)]
    return {"best": min(runs), "median": statistics.median(runs), "loops": number}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[100, 1_000, 10_000])
    parser.add_argument("--multi", type=int, default=32, help="leaves per multiproof")
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--min-time", type=float, default=0.2)
    parser.add_argument("--filter", default="", help="only run names containing this")
    parser.add_argument("--json", help="write results here instead of stdout")
    args = parser.parse_args()

    results = []
    roots = {}
    for n in args.sizes:
        roots[n] = {
            "standard": StandardMerkleTree.of(make_values(n), ENCODING).root,
            "simple": SimpleMerkleTree.of(make_hashes(n)).root,
        }
        for name, fn in build_cases(n, args.multi).items():
            if args.filter not in name:
                continue
            timing = time_case(fn, args.repeat, args.min_time)
            results.append({"name": name, "size": n, **timing})
            print(
                f"  {name:<36} n={n:<7} {timing['best'] * 1e6:>12.2f} µs",
                file=sys.stderr,
            )

    output = {
        "meta": {
            "murky_tree_version": version("murky-tree"),
            "murky_tree_path": murky_tree.__file__,
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
        "roots": {str(n): r for n, r in roots.items()},
        "results": results,
    }
    text = json.dumps(output, indent=2)
    if args.json:
        with open(args.json, "w") as f:
            f.write(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
