# Murky-Tree

*A Python library to generate Merkle trees and Merkle proofs forked from [@openzeppelin/merkle-tree](https://github.com/OpenZeppelin/merkle-tree) and [stakewise/multiproof](https://github.com/stakewise/multiproof)*

Well suited for airdrops and similar mechanisms in combination with OpenZeppelin Contracts MerkleProof utilities.
[`MerkleProof`]: <https://docs.openzeppelin.com/contracts/5.x/api/utils#MerkleProof>

## Quick Start

**uv**
``` shell
uv add murky-tree
```

**poetry**
``` shell
poetry add murky-tree
```

**pip**
``` shell
pip install murky-tree
```

### Building a Tree

``` python
import json

from murky_tree import StandardMerkleTree


# Get the values to include in the tree. (Note: Consider reading them from a file.)
values = [
    ["0x1111111111111111111111111111111111111111", 5000000000000000000],
    ["0x2222222222222222222222222222222222222222", 2500000000000000000],
]
# Build the Merkle tree. Set the encoding to match the values.
tree = StandardMerkleTree.of(values, ["address", "uint256"])
# Print the Merkle root. You will probably publish this value on chain in a smart contract.
print("Merkle Root:", tree.root)
# Write a file that describes the tree. You will distribute this to users so they can generate proofs for values in the tree.
with open("tree.json", "w") as file:
    json.dump(tree.to_json(), file)
```

### Obtaining a Proof

Assume we're looking to generate a proof for the entry that corresponds to address `0x11...11`.

```python
import json

from murky_tree import StandardMerkleTree


# Load the tree from the description that was generated previously.
with open("tree.json") as file:
    tree = StandardMerkleTree.from_json(json.load(file))

# Loop through the entries to find the one you're interested in.
for i, leaf in enumerate(tree.values):
    if leaf.value[0] == "0x1111111111111111111111111111111111111111":
        # Generate the proof using the index of the entry.
        proof = tree.get_proof(i)
        print("Value:", leaf.value)
        print("Proof:", proof)
```

In practice this might be done in a frontend application prior to submitting the proof on-chain, with the address looked up being that of the connected wallet.

Proving one leaf at a time, as above, is the common case. To prove several leaves
in a single proof, see [Multiproofs](#multiproofs) under Advanced usage.

### Validating a Proof in Solidity

Once the proof has been generated, it can be validated in Solidity using [`MerkleProof`] as in the following example:

```solidity
pragma solidity ^0.8.4;

import "@openzeppelin/contracts/utils/cryptography/MerkleProof.sol";

contract Verifier {
    bytes32 private root;

    constructor(bytes32 _root) {
        // (1)
        root = _root;
    }

    function verify(
        bytes32[] memory proof,
        address addr,
        uint256 amount
    ) public {
        // (2)
        bytes32 leaf = keccak256(bytes.concat(keccak256(abi.encode(addr, amount))));
        // (3)
        require(MerkleProof.verify(proof, root, leaf), "Invalid proof");
        // (4)
        // ...
    }
}
```

1. Store the tree root in your contract.
2. Compute the [leaf hash](#leaf-hash) for the provided `addr` and `amount` ABI encoded values.
3. Verify it using [`MerkleProof`]'s `verify` function.
4. Use the verification to make further operations on the contract. (Consider you may want to add a mechanism to prevent reuse of a leaf).

## Standard Merkle Trees

This library works on "standard" Merkle trees designed for Ethereum smart contracts. We have defined them with a few characteristics that make them secure and good for on-chain verification.

- The tree is shaped as a [complete binary tree](https://xlinux.nist.gov/dads/HTML/completeBinaryTree.html).
- The leaves are sorted.
- The leaves are the result of ABI encoding a series of values.
- The hash used is Keccak256.
- The leaves are double-hashed[^1] to prevent [second preimage attacks].

[second preimage attacks]: https://flawed.net.nz/2018/02/21/attacking-merkle-trees-with-a-second-preimage-attack/

## Simple Merkle Trees

Sometimes your leaves are already `bytes32` hashes and you don't want the standard ABI-encoding and double-hashing. `SimpleMerkleTree` builds a tree directly over raw `bytes32` leaves. It shares the same proof and verification machinery as `StandardMerkleTree`; only the leaf handling differs (the leaf is used as-is, with no hashing).

```python
from murky_tree import SimpleMerkleTree

# Leaves are already-computed 32-byte hashes, as hex strings or bytes.
leaves = [
    "0x1111111111111111111111111111111111111111111111111111111111111111",
    "0x2222222222222222222222222222222222222222222222222222222222222222",
]
tree = SimpleMerkleTree.of(leaves)
print("Merkle Root:", tree.root)

proof = tree.get_proof(0)
assert SimpleMerkleTree.verify(tree.root, leaves[0], proof)
```

Serialization works the same way as the standard tree, using the `simple-v1`
format. Use `dump()`/`load()` to keep a typed copy inside Python, and
`to_json()`/`from_json()` to write a file or interoperate with the JS library
(see [Serialization](#serialization-and-json-interoperability)):

```python
data = tree.dump()
tree = SimpleMerkleTree.load(data)

json_tree = tree.to_json()                  # JS-compatible dict
tree = SimpleMerkleTree.from_json(json_tree)
```

### Custom node hashing

By default, nodes are combined with the same sorted-pair Keccak256 as `StandardMerkleTree`. You can supply your own `node_hash`, for example to use a different hash function or add a domain separator:

```python
from eth_utils import keccak


def my_node_hash(a: bytes, b: bytes) -> bytes:
    lo, hi = (a, b) if a < b else (b, a)  # sort -> commutative
    return keccak(keccak(lo + hi))


tree = SimpleMerkleTree.of(leaves, node_hash=my_node_hash)
proof = tree.get_proof(0)
assert SimpleMerkleTree.verify(tree.root, leaves[0], proof, node_hash=my_node_hash)
```

The `node_hash` **must be commutative** (e.g. sort its two inputs), because proofs do not encode a sibling's left/right position — this is exactly why the default sorts the pair. A tree built with a custom node hash records `hash: "custom"` in its dump, and `load` then requires you to supply the same `node_hash` again.

## Tree representation

Under the hood the tree is not a graph of node objects. It is stored as a single
flat list of `2 * n - 1` hashes in binary-heap order (matching the
[`@openzeppelin/merkle-tree`](https://github.com/OpenZeppelin/merkle-tree) layout,
so a dumped tree is byte-for-byte compatible). For a tree of 4 leaves `L0..L3`:

```
 array index:   0      1      2      3    4    5    6
              +------+------+------+----+----+----+----+
    tree[]:   | root | H34  | H10  | L3 | L2 | L1 | L0 |
              +------+------+------+----+----+----+----+
                 \___ internal nodes __/   \___ leaves __/

 tree shape:                [0] root
                          /            \
                    [1] H34            [2] H10
                    /      \           /      \
                [3]        [4]      [5]        [6]
                 L3         L2       L1         L0
```

Leaves are placed at the end of the array (in reverse), then each internal node
is filled bottom-up as the sorted-pair Keccak256 of its two children, leaving the
root at index `0`. Because the layout is a heap, moving around the tree needs no
pointers — just index arithmetic:

```
 left_child(i)  = 2i + 1
 right_child(i) = 2i + 2
 parent(i)      = (i - 1) // 2
 sibling(i)     = i - 1 if i is even else i + 1
```

A proof for a leaf is just the chain of siblings collected while walking from the
leaf up to the root; verification folds them back together with the same hash to
recompute the root. This flat representation is both faster than a pointer-based
tree (contiguous memory, no per-node allocation) and what makes `dump`/`load`
interoperable with the JavaScript library for frontend applications.

### Serialization and JSON interoperability

There are two ways to serialize a tree, forming two independent round-trip pairs.
Choose based on where the data is going.

|                              | `dump()` ↔ `load()`                                    | `to_json()` ↔ `from_json()`                       |
| ---------------------------- | ------------------------------------------------------ | ------------------------------------------------- |
| Returns                      | a typed dataclass (`StandardMerkleTreeData` / `SimpleMerkleTreeData`) | a plain, JSON-ready `dict`          |
| Keys                         | snake_case (`tree_index`, `leaf_encoding`)             | camelCase (`treeIndex`, `leafEncoding`)           |
| Integer leaf values          | native Python `int`                                    | decimal strings (JavaScript-safe)                 |
| Simple tree's default `hash` | present, as `None`                                     | omitted                                            |
| Interop with `@openzeppelin/merkle-tree` | no                                         | **yes** — byte-for-byte                            |
| Use it for                   | keeping a typed, structured copy inside Python         | writing files / handing a tree to a frontend      |

**Use `to_json()` whenever the tree leaves your process** — persisting to disk,
sending it over the wire, or distributing a `tree.json` that a JavaScript
frontend will load. It emits the exact format the JS library produces, so it
loads there with `StandardMerkleTree.load(...)` / `SimpleMerkleTree.load(...)`,
and back here with `from_json`:

```python
import json

with open("tree.json", "w") as f:
    json.dump(tree.to_json(), f)                       # write (loadable by the JS library)

with open("tree.json") as f:
    tree = StandardMerkleTree.from_json(json.load(f))  # read back
```

**Use `dump()` when you stay inside Python** — to inspect the structured fields,
cache the description in memory, or hand it straight to `load()`. It returns a
typed dataclass, not JSON. Do **not** `json.dump` it for a frontend: its
snake_case keys and numeric big integers are not what the JS library expects, and
large integers written as JSON numbers would lose precision on the JS side.

```python
data = tree.dump()                     # StandardMerkleTreeData(...)
same = StandardMerkleTree.load(data)   # reconstruct from the dataclass
```

To achieve interoperability, `to_json`/`from_json` follow the JS library's
conventions rather than the Python dataclass API:

- Keys are **camelCase** (`treeIndex`, `leafEncoding`), not snake_case.
- The simple tree's `hash` key is present only for a custom node hash (omitted
  otherwise).
- Integer leaf values (`uint*`/`int*`) are serialized as **decimal strings**, so
  large `uint256` values survive JavaScript's `Number` precision limit;
  `from_json` parses them back to Python `int`s. This applies at any nesting
  depth — integers inside arrays and tuples/structs (e.g. `(address,uint256)`,
  `uint256[]`) are handled too, by walking the ABI type grammar.

The `reference/` folder contains a bun + TypeScript script that generates
cross-implementation test vectors with the real JS library; `tests/test_reference_vectors.py`
checks that `murky-tree` reproduces them and that this JSON format matches.

## Advanced usage

### Leaf Hash

The Standard Merkle Tree uses an opinionated double leaf hashing algorithm. For example, a leaf in the tree with value `[addr, amount]` can be computed in Solidity as follows:

```solidity
bytes32 leaf = keccak256(bytes.concat(keccak256(abi.encode(addr, amount))));
```

This is an opinionated design that we believe will offer the best out of the box experience for most users. However, there are advanced use cases where a different leaf hashing algorithm may be needed. For those, [`SimpleMerkleTree`](#simple-merkle-trees) builds a tree over raw `bytes32` leaves (which you can hash however you like) and supports a custom node hash.

### Multiproofs

Proving one leaf at a time (see [Obtaining a Proof](#obtaining-a-proof)) is the
common case, and **most people never need anything else** — if users only ever
prove a single entry (a typical airdrop claim), skip this section. A multiproof is
worth reaching for only when you verify *several* leaves together in one onchain
transaction — e.g. a "claim all" that settles a user's multiple allocations in a
single `multiProofVerify` call instead of one transaction per leaf. When you do
need that, pass the indices (or values) you want to prove:

```python
from murky_tree import StandardMerkleTree

values = [
    ["0x1111111111111111111111111111111111111111", 5000000000000000000],
    ["0x2222222222222222222222222222222222222222", 2500000000000000000],
    ["0x3333333333333333333333333333333333333333", 1000000000000000000],
]
tree = StandardMerkleTree.of(values, ["address", "uint256"])

multiproof = tree.get_multi_proof([0, 2])            # subset by index (or value)
assert tree.verify_multi_proof_leaf(multiproof)      # against the full tree
assert StandardMerkleTree.verify_multi_proof(        # from root + encoding alone
    tree.root, ["address", "uint256"], multiproof
)
```

Multiproofs require the proven leaves to be in tree order. This library knows the
whole tree, so it reorders them for you — `multiproof.leaves` may come back in a
different order than you requested, and that returned order is the one a smart
contract must submit. Keeping `sort_leaves=True` (the default) lets a contract
rebuild and order the leaves without any knowledge of the tree; disable it only to
represent trees built onchain by an iterative process, which complicates onchain
verification.

The multiproof format and its onchain verification are OpenZeppelin's; for the full
details see the [`@openzeppelin/merkle-tree` multiproof docs](https://github.com/OpenZeppelin/merkle-tree#leaf-ordering)
and [`MerkleProof`]'s `multiProofVerify`.

## API & Examples

> **Note**
> Consider reading the array of elements from a CSV file for easy interoperability with spreadsheets or other data processing pipelines.
>
> By default, leaves are sorted according to their hash. This is done so that multiproofs generated by the library can more easily be verified onchain. This can be disabled using the optional `sort_leaves` argument. See the [Multiproofs](#multiproofs) section for more details.

### `StandardMerkleTree`

```python3
from murky_tree import StandardMerkleTree
```

#### `StandardMerkleTree.of`

```python3
tree = StandardMerkleTree.of(
    [
        ["0x1111111111111111111111111111111111111111", 5000000000000000000],
        ["0x2222222222222222222222222222222222222222", 2500000000000000000],
    ],
    ["address", "uint256"],
    sort_leaves=True,
)
```

Creates a standard Merkle tree from an array of value tuples together with the ABI types used to encode each leaf.

The leaves are encoded with [`eth-abi`](https://eth-abi.readthedocs.io/) (via `eth_abi.encode`), so **both the type strings and the values must be in the form `eth-abi` expects** — Solidity ABI type names and their Python representations:

| ABI type              | Example type string          | Python value                          |
| --------------------- | ---------------------------- | ------------------------------------- |
| Unsigned/signed int   | `"uint256"`, `"int128"`      | `int` (e.g. `100`) — **not** a string |
| Address               | `"address"`                  | hex `str` (`"0x…"`)                    |
| Boolean               | `"bool"`                     | `bool`                                |
| String                | `"string"`                   | `str`                                 |
| Fixed/dynamic bytes   | `"bytes32"`, `"bytes"`       | `bytes` or hex `str`                  |
| Array                 | `"uint256[]"`, `"address[2]"`| `list`                                |
| Tuple / struct        | `"(address,uint256)"`        | `tuple`/`list` of its fields          |

Types nest arbitrarily, e.g. `"(address,uint256)[]"` or `"(uint8,(address,uint256[]))"` (a Solidity `enum` is encoded as its underlying `uint8`). Integers in particular must be passed as Python `int`s — `eth-abi` rejects decimal strings. When you serialize with `to_json` those integers are converted to strings for JavaScript, and `from_json` converts them back (see [Serialization](#serialization-and-json-interoperability)).

#### `StandardMerkleTree.load`

```python3
from murky_tree.standard import StandardMerkleTree, StandardMerkleTreeData, LeafValue

StandardMerkleTree.load(
    StandardMerkleTreeData(
        format="standard-v1",
        tree=["0x0000000000000000000000000000000000000000000000000000000000000000"],
        values=[LeafValue(value=[0], tree_index=0)],
        leaf_encoding=["uint256"],
    )
)
```

Loads the tree from a description previously returned by `tree.dump`.

#### `StandardMerkleTree.verify`

```python3
verified = StandardMerkleTree.verify(
    root,
    ["address", "uint256"],
    ["0x1111111111111111111111111111111111111111", 5000000000000000000],
    proof,
)
```

Returns a boolean that is `true` when the proof verifies that the value is contained in the tree given only the proof, Merkle root, and encoding.

#### `StandardMerkleTree.verify_multi_proof`

```python3
is_valid = StandardMerkleTree.verify_multi_proof(root, leaf_encoding, multiproof)
```

Returns a boolean that is `true` when the multiproof verifies that all the values are contained in the tree given only the multiproof, Merkle root, and leaf encoding.

#### Options

Allows to configure the behavior of the tree. The following options are available:

| Option        | Description                                                                       | Default |
|---------------| --------------------------------------------------------------------------------- | ------- |
| `sort_leaves` | Enable or disable sorted leaves. Sorting is strongly recommended for multiproofs. | `true`  |

#### `tree.root`

```python3
print(tree.root)
```

The root of the tree is a commitment on the values of the tree. It can be published (e.g., in a smart contract) to later prove that its values are part of the tree.

#### `tree.dump`

```python3
data = tree.dump()   # StandardMerkleTreeData / SimpleMerkleTreeData
```

Returns a typed dataclass describing the tree — the in-memory, snake_case counterpart to `load()`. Use it to keep a structured copy inside Python or to reconstruct the tree with `StandardMerkleTree.load(data)`. It is **not** JSON; to write a file or interoperate with the JavaScript library, use [`to_json`](#treeto_json) instead. See [Serialization](#serialization-and-json-interoperability) for the full comparison.

#### `tree.to_json`

```python3
import json

with open("tree.json", "w") as file:
    json.dump(tree.to_json(), file)
```

Returns a plain `dict` in the exact `@openzeppelin/merkle-tree` JSON format (camelCase keys, integer leaf values as decimal strings). This is the description you distribute to users or a frontend so they can generate proofs for their leaves of interest; read it back with `from_json`. It contains all the information needed to reproduce the tree, find the relevant leaves, and generate proofs.

#### `tree.get_proof`

```python3
proof = tree.get_proof(i)
```

Returns a proof for the `i`th value in the tree. Indices refer to the position of the values in the array from which the tree was constructed.

Also accepts a value instead of an index, but this will be less efficient. It will fail if the value is not found in the tree.

```python3
proof = tree.get_proof(value)  # e.g. ["0x1111111111111111111111111111111111111111", 5000000000000000000]
```

#### `tree.get_multi_proof`

```python3
multiproof = tree.get_multi_proof([i0, i1, ...])
print("proof:", multiproof.proof)
print("proof_flags:", multiproof.proof_flags)
print("leaves:", multiproof.leaves)
```

Returns a multiproof for the values at indices `i0, i1, ...`. Indices refer to the position of the values in the array from which the tree was constructed.

The multiproof returned contains an array with the leaves that are being proven. This array may be in a different order than that given by `i0, i1, ...`! The order returned is significant, as it is that in which the leaves must be submitted for verification (e.g., in a smart contract).

Also accepts values instead of indices, but this will be less efficient. It will fail if any of the values is not found in the tree.

```python3
multiproof = tree.get_multi_proof(
    [value1, value2]
)  # e.g. [["0x1111...1111", 5000000000000000000], ["0x2222...2222", 2500000000000000000]]
```

#### `tree.verify_leaf`

```python3
tree.verify_leaf(i, proof)
tree.verify_leaf(value, proof)  # e.g. ["0x1111111111111111111111111111111111111111", 5000000000000000000]
```

Returns a boolean that is `true` when the proof verifies that the value is contained in the tree.

#### `tree.verify_multi_proof_leaf`

```python3
from murky_tree import MultiProof

multi_proof = MultiProof(proof=proof, proof_flags=proof_flags, leaves=leaves)
tree.verify_multi_proof_leaf(multi_proof)
```

Returns a boolean that is `true` when the multi-proof verifies that the values are contained in the tree.

#### `tree.leaf_hash`

```python3
leaf = tree.leaf_hash(value)  # e.g. ["0x1111111111111111111111111111111111111111", 5000000000000000000]
```

Returns the leaf hash of the value, defined per tree type.

It corresponds to the following expression in Solidity:

```solidity
bytes32 leaf = keccak256(bytes.concat(keccak256(abi.encode(addr, amount))));
```

#### `Rendering the tree`

```python3
print(tree)
```

Returns a visual representation of the tree that can be useful for debugging.

## Testing

``` shell
uv sync
uv run pytest
```

## License & attribution

`murky-tree` is released under the [MIT License](LICENSE).

It is a Python fork of [`@openzeppelin/merkle-tree`](https://github.com/OpenZeppelin/merkle-tree),
derived by way of a Stakewise Labs Python port. The tree layout and JSON format are
kept byte-for-byte compatible with the original so trees can be shared with the
JavaScript library. Per the MIT License, the upstream copyright notices are retained
in [`LICENSE`](LICENSE):

- OpenZeppelin (zOS Global Limited and contributors) — original `@openzeppelin/merkle-tree`
- Stakewise Labs — Python port
