r"""Flat-array Merkle tree core.

The tree is stored as a single ``list[bytes]`` of ``2 * n - 1`` nodes in
binary-heap order -- there are no node objects or pointers. This mirrors the
layout of ``@openzeppelin/merkle-tree`` so that ``dump()`` serializes in a
byte-for-byte compatible order, and it reduces all navigation to index math.

Layout (example with 4 leaves ``L0..L3``)::

    array index:   0      1      2      3    4    5    6
                 +------+------+------+----+----+----+----+
        tree[]:  | root | H34  | H10  | L3 | L2 | L1 | L0 |
                 +------+------+------+----+----+----+----+
                    \___ internal nodes __/   \___ leaves __/

    tree shape:                [0] root
                             /            \
                       [1] H34            [2] H10
                       /      \           /      \
                   [3]        [4]      [5]        [6]
                    L3         L2       L1         L0

Leaves are written to the *end* of the array in reverse insertion order
(``tree[len - 1 - i] = leaf_i``); internal nodes are then filled bottom-up, each
the ``hash_pair`` of its two children, leaving the root at index 0. Reading the
tree in level order (top-to-bottom, left-to-right) is exactly array order.

Navigation is pure arithmetic on an index ``i`` (see the ``*_index`` helpers)::

    left_child(i)  = 2i + 1
    right_child(i) = 2i + 2
    parent(i)      = (i - 1) // 2
    sibling(i)     = i - 1 if i is even else i + 1

A node is a leaf exactly when its left-child index falls outside the array, so
no per-node flag is needed. ``get_proof`` walks parent-ward collecting each
sibling; ``process_proof`` folds those siblings back up with the node hash to
recompute the root. The default node hash (``hash_pair``) sorts each pair, which
makes the fold order-independent; ``make_merkle_tree`` / ``process_proof`` /
``process_multi_proof`` / ``is_valid_merkle_tree`` all accept a ``node_hash``
override so callers (e.g. ``SimpleMerkleTree``) can supply a custom one.
"""

from collections.abc import Callable
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

from murky_tree.utils import keccak

# A node hash combines two child nodes into their parent. The default,
# ``hash_pair``, sorts the pair so proofs need not encode left/right position;
# ``SimpleMerkleTree`` may supply a custom one.
NodeHash = Callable[[bytes, bytes], bytes]


@dataclass
class CoreMultiProof:
    leaves: list[bytes]
    proof: list[bytes]
    proof_flags: list[bool]


def hash_pair(a: bytes, b: bytes) -> bytes:
    if a < b:
        return keccak(a + b)
    return keccak(b + a)


def left_child_index(i: int) -> int:
    return 2 * i + 1


def right_child_index(i: int) -> int:
    return 2 * i + 2


def parent_index(i: int) -> int:
    if i > 0:
        return (i - 1) // 2
    raise ValueError("Root has no parent")


def sibling_index(i: int) -> int:
    if i > 0:
        return i - 1 if i % 2 == 0 else i + 1
    raise ValueError("Root has no siblings")


def is_tree_node(tree: list[bytes], i: int) -> bool:
    return 0 <= i < len(tree)


def is_internal_node(tree: list[bytes], i: int) -> bool:
    return is_tree_node(tree, left_child_index(i))


def is_leaf_node(tree: list[bytes], i: int) -> bool:
    return is_tree_node(tree, i) and not is_internal_node(tree, i)


def is_valid_merkle_node(node: bytes) -> bool:
    return len(node) == 32


def check_tree_node(tree: list[bytes], i: int) -> None:
    if not is_tree_node(tree, i):
        raise ValueError("Index is not in tree")


def check_internal_node(tree: list[bytes], i: int) -> None:
    if not is_internal_node(tree, i):
        raise ValueError("Index is not an internal tree node")


def check_leaf_node(tree: list[bytes], i: int) -> None:
    if not is_leaf_node(tree, i):
        raise ValueError("Index is not a leaf")


def check_valid_merkle_node(node: bytes) -> None:
    if not is_valid_merkle_node(node):
        raise ValueError("Merkle tree nodes must be byte array of length 32")


def make_merkle_tree(
    leaves: list[bytes], node_hash: NodeHash = hash_pair
) -> list[bytes]:
    for leaf in leaves:
        check_valid_merkle_node(leaf)

    if len(leaves) == 0:
        raise ValueError("Expected non-zero number of leaves")

    tree: list[bytes] = [b""] * (2 * len(leaves) - 1)

    for index, leaf in enumerate(leaves):
        tree[len(tree) - 1 - index] = leaf

    for i in range(len(tree) - 1 - len(leaves), -1, -1):
        tree[i] = node_hash(
            tree[left_child_index(i)],
            tree[right_child_index(i)],
        )
    return tree


def get_proof(tree: list[bytes], index: int) -> list[bytes]:
    check_leaf_node(tree, index)

    proof = []
    while index > 0:
        proof.append(tree[sibling_index(index)])
        index = parent_index(index)

    return proof


def process_proof(
    leaf: bytes, proof: list[bytes], node_hash: NodeHash = hash_pair
) -> bytes:
    check_valid_merkle_node(leaf)
    for item in proof:
        check_valid_merkle_node(item)
    result = leaf
    for item in proof:
        result = node_hash(result, item)
    return result


def get_multi_proof(tree: list[bytes], indices: list[int]) -> CoreMultiProof:
    for index in indices:
        check_leaf_node(tree, index)

    indices = sorted(indices, reverse=True)

    for prev_index, next_index in pairwise(indices):
        if prev_index == next_index:
            raise ValueError("Cannot prove duplicated index")

    stack = indices[:]
    proof = []
    proof_flags = []

    while len(stack) > 0 and stack[0] > 0:
        j = stack.pop(0)  # take from the beginning
        s = sibling_index(j)
        p = parent_index(j)

        if len(stack) and s == stack[0]:
            proof_flags.append(True)
            stack.pop(0)  # consume from the stack
        else:
            proof_flags.append(False)
            proof.append(tree[s])

        stack.append(p)

    if len(indices) == 0:
        proof.append(tree[0])

    return CoreMultiProof(
        leaves=[tree[i] for i in indices],
        proof=proof,
        proof_flags=proof_flags,
    )


def process_multi_proof(
    multiproof: CoreMultiProof, node_hash: NodeHash = hash_pair
) -> bytes:
    for leaf in multiproof.leaves:
        check_valid_merkle_node(leaf)

    for p in multiproof.proof:
        check_valid_merkle_node(p)

    if len(multiproof.proof) < len([x for x in multiproof.proof_flags if not x]):
        raise ValueError("Invalid multiproof format")

    if (
        len(multiproof.leaves) + len(multiproof.proof)
        != len(multiproof.proof_flags) + 1
    ):
        raise ValueError("Provided leaves and multiproof are not compatible")

    stack = multiproof.leaves.copy()
    proof = multiproof.proof.copy()

    for flag in multiproof.proof_flags:
        a = stack.pop(0)
        if flag:
            b = stack.pop(0)
        else:
            b = proof.pop(0)

        stack.append(node_hash(a, b))
    return pop_safe(stack) or proof.pop(0)


def is_valid_merkle_tree(tree: list[bytes], node_hash: NodeHash = hash_pair) -> bool:
    for i, node in enumerate(tree):
        if not is_valid_merkle_node(node):
            return False

        left = left_child_index(i)
        right = right_child_index(i)

        if right >= len(tree):
            if left < len(tree):
                return False
        elif node != node_hash(tree[left], tree[right]):
            return False

    return len(tree) > 0


def pop_safe(array: list[Any]) -> Any:
    try:
        return array.pop()
    except IndexError:
        return None
