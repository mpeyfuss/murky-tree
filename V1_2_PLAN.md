# v1.2.0: Pure Python performance improvements

Start a `v1.2` branch from commit `049b7e1`, the original Python implementation.
Preserve the existing Python API, accepted inputs, serialization formats, and
exception behavior. Keep the Rust implementation separately on the `v2` branch.

Implement each optimization in a separate commit so a future comparison runner
can measure its contribution independently. Do not carry over Rust packaging,
the native extension requirement, or v2's stricter input validation.

## 1. Calculate leaf hashes once during construction

**Files:** `murky_tree/merkletree.py`, `murky_tree/standard.py`,
`murky_tree/simple.py`.

Currently, `of()` calculates leaf hashes to build the tree, then the constructor
calculates them again to populate `_hash_lookup`.

- Add an optional, keyword-only private constructor argument:
  `_leaf_hashes: list[bytes] | None = None`.
- Pass the hashes already calculated by `of()` through the subclass constructor
  to `BaseMerkleTree`.
- Populate `_hash_lookup` from those hashes when provided. They must remain in
  original value order, regardless of the tree's leaf-sorting option.
- Compute hashes normally when the argument is omitted, preserving direct
  construction and `load()` behavior.
- Preserve the existing lookup behavior for duplicate leaf hashes.

For Standard trees, this removes a second round of ABI encoding and double
hashing for every leaf.

Limit reuse to construction. Do not introduce a persistent cache of mutable leaf
values: validation and proof generation must still detect values changed after
construction.

**Validation:** Count leaf-hash calls during construction; exercise sorted and
unsorted trees, duplicate values, direct construction, loading, and mutation
detection.

## 2. Replace front-of-list removal with queues

**File:** `murky_tree/core.py`.

Multiproof generation and processing currently use `list.pop(0)`, which shifts
all remaining elements. Use `collections.deque` for the working queues:

```python
from collections import deque

queue = deque(indices)
item = queue.popleft()
queue.append(parent)
```

- In `get_multi_proof()`, retain descending index sorting and duplicate-index
  validation, then create a deque for the traversal queue.
- In `process_multi_proof()`, use deques for both working values and supplied
  proof hashes.
- Replace front removals with `popleft()`. Preserve any end removals as `pop()`;
  do not change consumption order merely because a valid proof often ends with
  one value remaining.
- Preserve proof flags, returned leaf order, and empty-selection behavior.
- Keep the public `CoreMultiProof` fields as ordinary lists.
- Do not mutate caller-owned inputs.

Preserve the original validation and exception behavior. In particular, do not
copy v2's additional conversion of queue-underflow errors into `ValueError`.

**Validation:** Check empty, single-leaf, partial, and all-leaf selections;
duplicate and invalid indexes; malformed proofs; input immutability; and exact
agreement with the JavaScript reference vectors.

## 3. Pad Simple tree leaves directly

**File:** `murky_tree/simple.py`.

`format_leaf()` currently invokes the general ABI encoder for a single
`bytes32`. For inputs up to 32 bytes, this operation is right-padding with zeros:

```python
raw = _to_bytes32(value)
if len(raw) <= 32:
    return raw.ljust(32, b"\x00")
return abi_encode(["bytes32"], [raw])
```

- Preserve `_to_bytes32()` and its existing input normalization.
- Use direct padding for valid lengths.
- Keep the ABI encoder for oversized inputs so the existing exception behavior
  is preserved.

**Validation:** Compare results with `eth_abi.encode` for lengths 0 through 32.
Check oversized inputs and supported hex-string inputs, including their error
behavior.

## 4. Add a direct internal Keccak path

**Files:** `murky_tree/utils.py`, `murky_tree/core.py`,
`murky_tree/standard.py`.

Internal tree operations already produce bytes. They do not need the public
helper's handling of integers, text, and hex strings on every hash.

Introduce a private bytes-only helper using the existing dependency:

```python
from eth_hash.auto import keccak as _keccak_bytes
```

Use that helper in `hash_pair()`:

```python
def hash_pair(a: bytes, b: bytes) -> bytes:
    return _keccak_bytes(a + b if a < b else b + a)
```

Use it after ABI encoding in `standard_leaf_hash()`:

```python
encoded = abi_encode(types, values)
return _keccak_bytes(_keccak_bytes(encoded))
```

- Keep the public `utils.keccak()` signature, accepted input forms, conversions,
  and error behavior intact.
- Verify that the internal fast path preserves behavior for inputs accepted by
  the original core functions. Retain normalization where compatibility needs it.
- Keep `eth-hash[pycryptodome]` as a runtime dependency for v1.2.
- Continue using Ethereum Keccak-256, not standardized SHA3-256.

This reduces Python wrapper overhead. The cryptographic hashing itself already
executes in native code through PyCryptodome.

**Validation:** Check known Keccak vectors, sorted-pair hashing, Standard leaf
hashes, custom hash callbacks, and all public Keccak input forms and errors.

## 5. Verify compatibility and prepare version 1.2.0

**Files:** `tests/`, `pyproject.toml`, `uv.lock`.

- Run the existing tests and canonical OpenZeppelin reference-vector tests.
- Add targeted regression tests for the changes above.
- Preserve v1.1's accepted inputs and exceptions instead of importing v2's
  stricter `list[bytes]` boundary behavior.
- Set the Python package version to `1.2.0` and update `uv.lock`.
- Retain the original Python build system and supported Python versions.
- Build the distribution and test an installed package outside the source tree.

Use the repository's existing lint, formatting, and type checks as well as
pytest. The reference generator and vectors in `reference/` remain the canonical
compatibility reference.

## Later: compare all implementations fairly

Create one benchmark runner that accepts named Git revisions and uses temporary
Git worktrees and separate virtual environments. It must not switch or modify
the user's working branch.

Compare:

1. Original Python at `049b7e1`.
2. Optimized Python at the completed v1.2 commit.
3. Rust at the completed v2 commit.

Use identical benchmark code and deterministic inputs for every revision.
Exercise common valid public operations: Standard/Simple construction, proof and
multiproof generation, verification, and validation. Check roots and proofs for
agreement before timing.

Exclude installation and compilation from timings. Use release builds for Rust,
a common Python version, warmups, repeated measurements, and comparable
dependency versions where supported. Record exact commit IDs, dependency
versions, environment details, medians, and variation.

Any compatibility adapter should only translate inputs or outputs; it must not
replace the algorithm being measured. Keep the comparison runner outside the
individual version implementations so the same workload can measure every
revision.

These measurements should distinguish the benefit of the Python optimizations
from the additional benefit of Rust. Do not reuse the earlier original-Python
versus Rust speedup claims as an estimate of that isolated Rust benefit.
