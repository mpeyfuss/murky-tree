from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Generic

from eth_abi import encode as abi_encode
from eth_typing import HexStr
from eth_utils import to_bytes, to_hex

from murky_tree.core import hash_pair
from murky_tree.merkletree import BaseMerkleTree, LeafValue, MultiProof, T, build_tree
from murky_tree.utils import (
    decode_values_from_json,
    encode_values_for_json,
    keccak,
)


@dataclass
class StandardMerkleTreeData(Generic[T]):
    tree: list[HexStr]
    values: list[LeafValue[T]]
    leaf_encoding: list[str]
    format: str = "standard-v1"


def standard_leaf_hash(values: Sequence[Any], types: list[str]) -> bytes:
    return keccak(keccak(abi_encode(types, values)))


class StandardMerkleTree(BaseMerkleTree[T]):
    leaf_encoding: list[str]

    def __init__(
        self, tree: list[bytes], values: list[LeafValue[T]], leaf_encoding: list[str]
    ):
        self.leaf_encoding = leaf_encoding
        super().__init__(tree, values)

    def _leaf_hash(self, value: T) -> bytes:
        return standard_leaf_hash(value, self.leaf_encoding)

    @staticmethod
    def of(
        values: list[T], leaf_encoding: list[str], sort_leaves: bool = True
    ) -> "StandardMerkleTree[T]":
        leaf_hashes = [standard_leaf_hash(value, leaf_encoding) for value in values]
        tree, indexed_values = build_tree(values, leaf_hashes, sort_leaves, hash_pair)
        return StandardMerkleTree(tree, indexed_values, leaf_encoding)

    @staticmethod
    def load(data: StandardMerkleTreeData[T]) -> "StandardMerkleTree[T]":
        if data.format != "standard-v1":
            raise ValueError(f"Unknown format '{data.format}'")
        return StandardMerkleTree(
            [to_bytes(hexstr=x) for x in data.tree],
            data.values,
            data.leaf_encoding,
        )

    @staticmethod
    def verify(
        root: HexStr, leaf_encoding: list[str], leaf_value: T, proof: list[HexStr]
    ) -> bool:
        leaf_hash = standard_leaf_hash(leaf_value, leaf_encoding)
        return StandardMerkleTree._static_verify(root, leaf_hash, proof, hash_pair)

    @staticmethod
    def verify_multi_proof(
        root: HexStr, leaf_encoding: list[str], multiproof: MultiProof
    ) -> bool:
        leaf_hashes = [
            standard_leaf_hash(value, leaf_encoding) for value in multiproof.leaves
        ]
        return StandardMerkleTree._static_verify_multi_proof(
            root, leaf_hashes, multiproof, hash_pair
        )

    def dump(self) -> StandardMerkleTreeData[T]:
        return StandardMerkleTreeData(
            format="standard-v1",
            tree=[to_hex(v) for v in self.tree],
            values=self.values,
            leaf_encoding=self.leaf_encoding,
        )

    def to_json(self) -> dict:
        return {
            "format": "standard-v1",
            "tree": [to_hex(v) for v in self.tree],
            "values": [
                {
                    "value": encode_values_for_json(v.value, self.leaf_encoding),
                    "treeIndex": v.tree_index,
                }
                for v in self.values
            ],
            "leafEncoding": self.leaf_encoding,
        }

    @staticmethod
    def from_json(data: dict) -> "StandardMerkleTree[T]":
        leaf_encoding = data["leafEncoding"]
        tree_data = StandardMerkleTreeData(
            tree=data["tree"],
            values=[
                LeafValue(
                    value=decode_values_from_json(item["value"], leaf_encoding),
                    tree_index=item["treeIndex"],
                )
                for item in data["values"]
            ],
            leaf_encoding=leaf_encoding,
            format=data.get("format", "standard-v1"),
        )
        return StandardMerkleTree.load(tree_data)
