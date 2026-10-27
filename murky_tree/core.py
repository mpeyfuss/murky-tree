"""Adapter for the required Rust Merkle core.

Default hashing and proof algorithms always use Rust. The callback branches
retain only the Python orchestration needed for user-supplied node hashes.
Proof generation transfers indices rather than copying the entire tree.
"""

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from murky_tree import _native as native
from murky_tree.utils import keccak

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
    if node_hash is hash_pair:
        return native.make_merkle_tree(leaves)

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
    return [tree[i] for i in native.proof_indices(len(tree), index)]


def process_proof(
    leaf: bytes, proof: list[bytes], node_hash: NodeHash = hash_pair
) -> bytes:
    if node_hash is hash_pair:
        return native.process_proof(leaf, proof)

    check_valid_merkle_node(leaf)
    for item in proof:
        check_valid_merkle_node(item)
    result = leaf
    for item in proof:
        result = node_hash(result, item)
    return result


def get_multi_proof(tree: list[bytes], indices: list[int]) -> CoreMultiProof:
    for i in indices:
        check_leaf_node(tree, i)
    leaves, proof, flags = native.multi_proof_indices(len(tree), indices)
    return CoreMultiProof([tree[i] for i in leaves], [tree[i] for i in proof], flags)


def process_multi_proof(
    multiproof: CoreMultiProof, node_hash: NodeHash = hash_pair
) -> bytes:
    if node_hash is hash_pair:
        return native.process_multi_proof(
            multiproof.leaves, multiproof.proof, multiproof.proof_flags
        )

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

    stack = deque(multiproof.leaves)
    proof = deque(multiproof.proof)

    for flag in multiproof.proof_flags:
        if len(stack) < (2 if flag else 1):
            raise ValueError("Invalid multiproof format")
        a = stack.popleft()
        if flag:
            b = stack.popleft()
        else:
            b = proof.popleft()

        stack.append(node_hash(a, b))
    return stack.pop() if stack else proof.popleft()


def is_valid_merkle_tree(tree: list[bytes], node_hash: NodeHash = hash_pair) -> bool:
    if node_hash is hash_pair:
        return native.is_valid_merkle_tree(tree)

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
