# Reference test vectors

Cross-implementation test vectors generated with the **original**
[`@openzeppelin/merkle-tree`](https://github.com/OpenZeppelin/merkle-tree) JS
library. The Python port (`murky-tree`) is tested against these vectors by
`tests/test_reference_vectors.py`, so that "compatible with the JS library" is
independently verified rather than assumed by the self-referential unit tests.

`vectors.json` is committed, so the Python tests run without bun installed.

## Regenerating

Requires [bun](https://bun.sh).

```shell
bun install       # restore deps from bun.lock
bun run generate  # rewrite vectors.json
```

Regeneration is deterministic — re-running produces no diff. Regenerate (and
review the diff) whenever the `@openzeppelin/merkle-tree` version in
`package.json` changes, then run `uv run pytest` from the repo root to confirm
the Python library still matches.

## What's in `vectors.json`

A top-level `{ generator, version, cases }`. Each case records:

- `input` — everything needed to rebuild the tree with `murky-tree`
  (`leafEncoding`, `sortLeaves`, `nodeHash` = `"default"`/`"custom"`, `values`).
- `root`, `tree` (flat binary-heap array), `leafHashes` (per input value),
  `proofs` (per input value), `multiProofs` (`{ indices, leaves, proof, proofFlags }`).
- `dump` — the raw JS `tree.dump()` JSON, used to verify that `murky-tree`'s
  `to_json()` / `from_json()` speak the exact same (camelCase) format.

Cases cover both `StandardMerkleTree` and `SimpleMerkleTree`, with `sortLeaves`
on and off, and a custom commutative `nodeHash` for the simple tree.
