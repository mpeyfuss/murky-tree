from collections.abc import Sequence
from dataclasses import dataclass

from eth_abi import encode as abi_encode
from eth_typing import HexStr
from eth_utils import to_bytes, to_hex

from murky_tree.core import NodeHash, hash_pair
from murky_tree.merkletree import BaseMerkleTree, LeafValue, MultiProof, build_tree

BytesLike = bytes | HexStr


def _to_bytes32(value: BytesLike) -> bytes:
    return to_bytes(hexstr=value) if isinstance(value, str) else bytes(value)


def format_leaf(value: BytesLike) -> bytes:
    """Normalize/validate a leaf to its 32-byte form.

    Mirrors OpenZeppelin's ``formatLeaf``: unlike the standard tree, the leaf is
    used as-is (no keccak) -- it is only ABI-encoded as a ``bytes32`` to validate
    the length and pad if short.
    """
    return abi_encode(["bytes32"], [_to_bytes32(value)])


@dataclass
class SimpleMerkleTreeData:
    tree: list[HexStr]
    values: list[LeafValue[HexStr]]
    format: str = "simple-v1"
    # "custom" when the tree was built with a non-default node hash; otherwise None.
    hash: str | None = None


class SimpleMerkleTree(BaseMerkleTree[bytes]):
    """A Merkle tree over already-hashed ``bytes32`` leaves.

    Unlike ``StandardMerkleTree`` the leaves are not ABI-encoded and
    double-hashed -- they are used directly. A custom ``node_hash`` may be
    supplied; it defaults to the standard sorted-pair keccak256.

    Note: a custom ``node_hash`` must be commutative (e.g. sort its two inputs),
    because proofs do not encode a sibling's left/right position. The default
    sorts the pair for exactly this reason.
    """

    def __init__(
        self,
        tree: list[bytes],
        values: list[LeafValue[bytes]],
        node_hash: NodeHash | None = None,
    ):
        super().__init__(tree, values, node_hash)
        self._custom_node_hash = node_hash is not None

    def _leaf_hash(self, value: bytes) -> bytes:
        return format_leaf(value)

    @staticmethod
    def of(
        values: Sequence[BytesLike],
        sort_leaves: bool = True,
        node_hash: NodeHash | None = None,
    ) -> "SimpleMerkleTree":
        leaves = [_to_bytes32(v) for v in values]
        leaf_hashes = [format_leaf(leaf) for leaf in leaves]
        tree, indexed_values = build_tree(
            leaves, leaf_hashes, sort_leaves, node_hash or hash_pair
        )
        return SimpleMerkleTree(tree, indexed_values, node_hash)

    @staticmethod
    def load(
        data: SimpleMerkleTreeData, node_hash: NodeHash | None = None
    ) -> "SimpleMerkleTree":
        if data.format != "simple-v1":
            raise ValueError(f"Unknown format '{data.format}'")
        if (node_hash is not None) != (data.hash == "custom"):
            raise ValueError(
                "Data does not expect a custom node hashing function"
                if node_hash is not None
                else "Data expects a custom node hashing function"
            )
        values = [
            LeafValue(value=_to_bytes32(v.value), tree_index=v.tree_index)
            for v in data.values
        ]
        tree = SimpleMerkleTree(
            [to_bytes(hexstr=x) for x in data.tree], values, node_hash
        )
        tree.validate()
        return tree

    @staticmethod
    def verify(
        root: HexStr,
        leaf: BytesLike,
        proof: list[HexStr],
        node_hash: NodeHash | None = None,
    ) -> bool:
        return SimpleMerkleTree._static_verify(
            root, format_leaf(leaf), proof, node_hash or hash_pair
        )

    @staticmethod
    def verify_multi_proof(
        root: HexStr, multiproof: MultiProof, node_hash: NodeHash | None = None
    ) -> bool:
        leaf_hashes = [format_leaf(leaf) for leaf in multiproof.leaves]
        return SimpleMerkleTree._static_verify_multi_proof(
            root, leaf_hashes, multiproof, node_hash or hash_pair
        )

    def dump(self) -> SimpleMerkleTreeData:
        return SimpleMerkleTreeData(
            format="simple-v1",
            tree=[to_hex(v) for v in self.tree],
            values=[
                LeafValue(value=to_hex(v.value), tree_index=v.tree_index)
                for v in self.values
            ],
            hash="custom" if self._custom_node_hash else None,
        )

    @staticmethod
    def from_json(data: dict, node_hash: NodeHash | None = None) -> "SimpleMerkleTree":
        tree_data = SimpleMerkleTreeData(
            tree=data["tree"],
            values=[LeafValue(**item) for item in data["values"]],
            format=data.get("format", "simple-v1"),
            hash=data.get("hash"),
        )
        return SimpleMerkleTree.load(tree_data, node_hash)
