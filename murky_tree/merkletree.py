"""Shared base for the Merkle tree variants.

``BaseMerkleTree`` holds everything common to ``StandardMerkleTree`` and
``SimpleMerkleTree`` -- the flat ``tree``/``values`` state, the hash lookup, and
all of the proof/verify/validate/render logic. Subclasses supply only three
things: how a leaf value is hashed (``_leaf_hash``), how the tree serializes
(``dump``), and the static constructors (``of``/``load``/``verify``). This
mirrors OpenZeppelin's ``MerkleTreeImpl`` base.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from eth_typing import HexStr
from eth_utils import to_bytes, to_hex

from murky_tree.core import (
    CoreMultiProof,
    NodeHash,
    get_multi_proof,
    get_proof,
    hash_pair,
    is_valid_merkle_tree,
    left_child_index,
    make_merkle_tree,
    process_multi_proof,
    process_proof,
    right_child_index,
)
from murky_tree.utils import check_bounds

T = TypeVar("T", bound=Sequence[Any])


@dataclass
class LeafValue(Generic[T]):
    value: T
    tree_index: int


@dataclass
class MultiProof(Generic[T]):
    """
    User-friendly version of multiproof, compare with CoreMultiProof
    """

    leaves: list[T]
    proof: list[HexStr]
    proof_flags: list[bool]


def build_tree(
    values: list[T],
    leaf_hashes: list[bytes],
    sort_leaves: bool,
    node_hash: NodeHash,
) -> tuple[list[bytes], list[LeafValue[T]]]:
    """Build the flat tree and the value->tree_index mapping.

    Shared by every ``of`` constructor: sort the leaves by hash (if requested),
    build the tree with ``node_hash``, then record where each original value
    landed. ``leaf_hashes[i]`` is the leaf hash of ``values[i]``.
    """
    if sort_leaves:
        order = sorted(range(len(leaf_hashes)), key=lambda i: leaf_hashes[i])
    else:
        order = list(range(len(leaf_hashes)))

    tree = make_merkle_tree([leaf_hashes[i] for i in order], node_hash)

    indexed_values = [LeafValue(value=v, tree_index=0) for v in values]
    for leaf_index, original_index in enumerate(order):
        indexed_values[original_index].tree_index = len(tree) - leaf_index - 1

    return tree, indexed_values


class BaseMerkleTree(ABC, Generic[T]):
    tree: list[bytes]
    values: list[LeafValue[T]]
    _hash_lookup: dict[HexStr, int]
    _node_hash: NodeHash

    def __init__(
        self,
        tree: list[bytes],
        values: list[LeafValue[T]],
        node_hash: NodeHash | None = None,
    ):
        self.tree = tree
        self.values = values
        self._node_hash = node_hash or hash_pair
        self._hash_lookup = {}
        for index, leaf_value in enumerate(values):
            self._hash_lookup[to_hex(self._leaf_hash(leaf_value.value))] = index

    @abstractmethod
    def _leaf_hash(self, value: T) -> bytes:
        """Hash a single leaf value into its 32-byte tree node."""

    @abstractmethod
    def dump(self) -> Any:
        """Return a serializable description of the tree."""

    @abstractmethod
    def to_json(self) -> dict:
        """Serialize to the ``@openzeppelin/merkle-tree`` JSON format.

        The keys are camelCase (``treeIndex``, ``leafEncoding``) so the output is
        directly loadable by the JS library, unlike the snake_case Python
        dataclasses.
        """

    @property
    def root(self) -> HexStr:
        return to_hex(self.tree[0])

    def validate(self) -> None:
        for i in range(len(self.values)):
            self._validate_value(i)

        if not is_valid_merkle_tree(self.tree, self._node_hash):
            raise ValueError("Merkle tree is invalid")

    def leaf_hash(self, leaf: T) -> HexStr:
        return to_hex(self._leaf_hash(leaf))

    def leaf_lookup(self, leaf: T) -> int:
        v = self._hash_lookup[self.leaf_hash(leaf)]
        if v is None:
            raise ValueError("Leaf is not in tree")
        return v

    def get_proof(self, leaf: T | int) -> list[HexStr]:
        # input validity
        value_index: int = leaf  # type: ignore
        if not isinstance(leaf, int):
            value_index = self.leaf_lookup(leaf)
        self._validate_value(value_index)

        # rebuild tree index and generate proof
        tree_index = self.values[value_index].tree_index
        proof = get_proof(self.tree, tree_index)

        # check proof
        leaf_hash = self.tree[tree_index]
        implied_root = process_proof(leaf_hash, proof, self._node_hash)

        if implied_root != self.tree[0]:
            raise ValueError("Unable to prove value")

        return [to_hex(p) for p in proof]

    def get_multi_proof(self, leaves: list[int] | list[T]) -> MultiProof:
        # input validity
        value_indices: list[int] = []
        for leaf in leaves:
            if isinstance(leaf, int):
                value_indices.append(leaf)
            else:
                value_indices.append(self.leaf_lookup(leaf))

        for value in value_indices:
            self._validate_value(value)

        # rebuild tree indices and generate proof
        indices = [self.values[i].tree_index for i in value_indices]
        proof = get_multi_proof(self.tree, indices)

        # check proof
        implied_root = process_multi_proof(proof, self._node_hash)
        if implied_root != self.tree[0]:
            raise ValueError("Unable to prove values")

        # return multiproof in hex format
        return MultiProof(
            leaves=[
                self.values[self._hash_lookup[to_hex(hash)]].value
                for hash in proof.leaves
            ],
            proof=[to_hex(x) for x in proof.proof],
            proof_flags=proof.proof_flags,
        )

    def verify_leaf(self, leaf: T | int | LeafValue[T], proof: list[HexStr]) -> bool:
        return self._verify_leaf(
            self._get_leaf_hash(leaf), [to_bytes(hexstr=p) for p in proof]
        )

    def _verify_leaf(self, leaf_hash: bytes, proof: list[bytes]) -> bool:
        implied_root = process_proof(leaf_hash, proof, self._node_hash)
        return implied_root == self.tree[0]

    def verify_multi_proof_leaf(self, multiproof: MultiProof) -> bool:
        return self._verify_multi_proof_leaf(
            CoreMultiProof(
                leaves=[self._get_leaf_hash(leaf) for leaf in multiproof.leaves],
                proof=[to_bytes(hexstr=p) for p in multiproof.proof],
                proof_flags=multiproof.proof_flags,
            )
        )

    def _verify_multi_proof_leaf(self, multi_proof: CoreMultiProof) -> bool:
        implied_root = process_multi_proof(multi_proof, self._node_hash)
        return implied_root == self.tree[0]

    @staticmethod
    def _static_verify(
        root: HexStr, leaf_hash: bytes, proof: list[HexStr], node_hash: NodeHash
    ) -> bool:
        """Stateless single-proof check shared by the subclasses' ``verify``."""
        implied_root = process_proof(
            leaf_hash, [to_bytes(hexstr=x) for x in proof], node_hash
        )
        return implied_root == to_bytes(hexstr=root)

    @staticmethod
    def _static_verify_multi_proof(
        root: HexStr,
        leaf_hashes: list[bytes],
        multiproof: MultiProof,
        node_hash: NodeHash,
    ) -> bool:
        """Stateless multiproof check shared by ``verify_multi_proof``."""
        implied_root = process_multi_proof(
            CoreMultiProof(
                leaves=leaf_hashes,
                proof=[to_bytes(hexstr=x) for x in multiproof.proof],
                proof_flags=multiproof.proof_flags,
            ),
            node_hash,
        )
        return implied_root == to_bytes(hexstr=root)

    def _validate_value(self, value_index: int) -> bytes:
        check_bounds(self.values, value_index)
        leaf = self.values[value_index]
        check_bounds(self.tree, leaf.tree_index)
        leaf_hash = self._leaf_hash(leaf.value)

        if leaf_hash != self.tree[leaf.tree_index]:
            raise ValueError("Merkle tree does not contain the expected value")
        return leaf_hash

    def _get_leaf_hash(self, leaf: T | int | LeafValue[T]) -> bytes:
        if isinstance(leaf, int):
            return self._validate_value(leaf)
        if isinstance(leaf, LeafValue):
            return self._leaf_hash(leaf.value)
        return self._leaf_hash(leaf)

    def __str__(self):
        if len(self.tree) == 0:
            raise ValueError("Expected non-zero number of nodes")

        stack: list = [[0, []]]
        lines: list = []

        while len(stack) > 0:
            i, path = stack.pop()
            s = ""

            if len(path):
                s += (
                    "".join([["   ", "│  "][p] for p in path[:-1]])
                    + ["└─ ", "├─ "][path[-1]]
                )
            s += str(i) + ") " + to_hex(self.tree[i])[2:]

            lines.append(s)
            if right_child_index(i) < len(self.tree):
                stack.append([right_child_index(i), path + [0]])
                stack.append([left_child_index(i), path + [1]])

        return "\n".join(lines)
