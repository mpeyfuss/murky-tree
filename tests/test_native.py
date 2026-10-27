"""Native adapter invariants and edge cases; canonical vectors live in test_reference_vectors."""

import itertools
import random

import pytest
from eth_abi import encode
from eth_hash.auto import keccak

from murky_tree import SimpleMerkleTree, StandardMerkleTree, core
from murky_tree.simple import format_leaf


@pytest.mark.parametrize("size", [1, 2, 3, 5, 8, 17, 64, 129])
def test_randomized_proofs(size):
    rng = random.Random(size)
    leaves = [rng.randbytes(32) for _ in range(size)]
    if size > 2:
        leaves[1] = leaves[0]  # repeated values are valid
    tree = core.make_merkle_tree(leaves)
    assert all(type(node) is bytes for node in tree)
    assert core.is_valid_merkle_tree(tree)
    for i in range(size - 1, len(tree)):
        proof = core.get_proof(tree, i)
        assert core.process_proof(tree[i], proof) == tree[0]
    for count in sorted({0, 1, size // 2, size}):
        indices = rng.sample(range(size - 1, len(tree)), count)
        before = indices.copy()
        mp = core.get_multi_proof(tree, indices)
        assert indices == before
        assert core.process_multi_proof(mp) == tree[0]
    tree[0] = b"\xff" * 32
    if size > 1:
        assert not core.is_valid_merkle_tree(tree)


def test_all_small_multiproof_subsets():
    for n in range(1, 8):
        tree = core.make_merkle_tree([keccak(bytes([i])) for i in range(n)])
        for count in range(n + 1):
            for indices in itertools.combinations(range(n - 1, len(tree)), count):
                mp = core.get_multi_proof(tree, list(indices))
                assert core.process_multi_proof(mp) == tree[0]


@pytest.mark.parametrize("length", [0, 1, 31, 33, 64])
def test_invalid_node_lengths(length):
    node = b"a" * length
    with pytest.raises(ValueError, match="length 32"):
        core.make_merkle_tree([node])
    with pytest.raises(ValueError, match="length 32"):
        core.process_proof(node, [])
    with pytest.raises(ValueError, match="length 32"):
        core.process_proof(b"a" * 32, [node])
    with pytest.raises(ValueError, match="length 32"):
        core.process_multi_proof(core.CoreMultiProof([], [node], []))
    assert not core.is_valid_merkle_tree([node])


def test_invalid_indices_and_empty_trees():
    with pytest.raises(ValueError, match="non-zero"):
        core.make_merkle_tree([])
    assert not core.is_valid_merkle_tree([])
    tree = core.make_merkle_tree([b"a" * 32, b"b" * 32])
    for index in [-1, 0, 3, 2**100]:
        with pytest.raises(ValueError, match="not a leaf"):
            core.get_proof(tree, index)
        with pytest.raises(ValueError, match="not a leaf"):
            core.get_multi_proof(tree, [index])
    with pytest.raises(ValueError, match="duplicated"):
        core.get_multi_proof(tree, [1, 1])
    assert not core.is_valid_merkle_tree(tree[:2])


@pytest.mark.parametrize(
    "leaves,proof,flags,message",
    [
        ([], [], [], "not compatible"),
        ([], [], [False], "Invalid multiproof"),
        ([], [b"a" * 32, b"b" * 32], [True], "Invalid multiproof"),
    ],
)
@pytest.mark.parametrize("custom", [False, True])
def test_malformed_multiproofs(leaves, proof, flags, message, custom):
    with pytest.raises(ValueError, match=message):
        node_hash = (
            (lambda a, b: keccak(min(a, b) + max(a, b))) if custom else core.hash_pair
        )
        core.process_multi_proof(core.CoreMultiProof(leaves, proof, flags), node_hash)


def test_custom_callback_used():
    calls = []

    def custom(a, b):
        calls.append((a, b))
        return keccak(keccak(min(a, b) + max(a, b)))

    leaves = [bytes([i]) * 32 for i in range(7)]
    tree = core.make_merkle_tree(leaves, custom)
    assert len(calls) == 6
    assert core.is_valid_merkle_tree(tree, custom)
    mp = core.get_multi_proof(tree, [6, 8, 12])
    assert core.process_multi_proof(mp, custom) == tree[0]
    assert core.process_proof(tree[6], core.get_proof(tree, 6), custom) == tree[0]


@pytest.mark.parametrize("length", range(34))
def test_simple_padding_matches_eth_abi(length):
    value = b"a" * length
    if length <= 32:
        assert format_leaf(value) == encode(["bytes32"], [value])
    else:
        from eth_abi.exceptions import ValueOutOfBounds

        with pytest.raises(ValueOutOfBounds):
            format_leaf(value)


def test_mutable_tree_remains_authoritative():
    tree = SimpleMerkleTree.of([b"a" * 32, b"b" * 32, b"c" * 32])
    tree.tree[0] = b"x" * 32
    with pytest.raises(ValueError, match="Unable to prove"):
        tree.get_proof(0)
    standard = StandardMerkleTree.of([[1], [2]], ["uint256"])
    standard.values[0].value[0] = 3
    with pytest.raises(ValueError, match="expected value"):
        standard.get_proof(0)


def test_custom_callback_exception_propagates():
    def fail(a, b):
        raise RuntimeError("callback failed")

    with pytest.raises(RuntimeError, match="callback failed"):
        core.make_merkle_tree([b"a" * 32, b"b" * 32], fail)
