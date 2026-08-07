import pytest
from eth_utils import to_hex

from murky_tree import SimpleMerkleTree, StandardMerkleTree
from murky_tree.merkletree import LeafValue
from murky_tree.simple import SimpleMerkleTreeData
from murky_tree.standard import standard_leaf_hash
from murky_tree.utils import keccak

ZERO_BYTES = bytes(32)


def make_tree(s: str, sort_leaves: bool = True) -> tuple[list[bytes], SimpleMerkleTree]:
    leaves = [keccak(text=x) for x in s]
    tree = SimpleMerkleTree.of(leaves, sort_leaves)
    return leaves, tree


# a custom node hash, distinct from the default but still commutative (sorts its
# inputs) -- proofs are position-less, so an order-sensitive hash cannot verify.
def custom_node_hash(a: bytes, b: bytes) -> bytes:
    lo, hi = (a, b) if a < b else (b, a)
    return keccak(keccak(lo + hi))


class TestSimpleMerkleTree:
    @pytest.mark.parametrize("sort_leaves", (True, False))
    def test_valid_single_proofs(self, sort_leaves):
        leaves, tree = make_tree("abcdef", sort_leaves)
        tree.validate()

        for index, leaf in enumerate(tree.values):
            proof1 = tree.get_proof(index)
            proof2 = tree.get_proof(leaf.value)
            assert proof1 == proof2
            assert tree.verify_leaf(index, proof1)
            assert tree.verify_leaf(leaf.value, proof1)
            assert SimpleMerkleTree.verify(tree.root, leaf.value, proof1)
            # a hex-string leaf must verify identically to the bytes form
            assert SimpleMerkleTree.verify(tree.root, to_hex(leaf.value), proof1)

    @pytest.mark.parametrize("sort_leaves", (True, False))
    def test_invalid_single_proofs(self, sort_leaves):
        leaves, tree = make_tree("abcdef", sort_leaves)
        _, other_tree = make_tree("abc", sort_leaves)
        leaf = leaves[0]
        invalid_proof = other_tree.get_proof(leaf)
        assert not tree.verify_leaf(leaf, invalid_proof)
        assert not SimpleMerkleTree.verify(tree.root, leaf, invalid_proof)

    @pytest.mark.parametrize("sort_leaves", (True, False))
    def test_valid_multiproofs(self, sort_leaves):
        leaves, tree = make_tree("abcdef", sort_leaves)
        tree.validate()

        for ids in [
            [],
            [0, 1],
            [0, 1, 5],
            [1, 3, 4, 5],
            [0, 2, 4, 5],
            [0, 1, 2, 3, 4, 5],
        ]:
            proof1 = tree.get_multi_proof(ids)
            proof2 = tree.get_multi_proof([leaves[i] for i in ids])
            assert proof1 == proof2
            assert tree.verify_multi_proof_leaf(proof1)
            assert SimpleMerkleTree.verify_multi_proof(tree.root, proof1)

    @pytest.mark.parametrize("sort_leaves", (True, False))
    def test_invalid_multiproofs(self, sort_leaves):
        leaves, tree = make_tree("abcdef", sort_leaves)
        _, other_tree = make_tree("abc", sort_leaves)
        other_leaves = [keccak(text=x) for x in "abc"]
        multi_proof = other_tree.get_multi_proof(other_leaves)
        assert not tree.verify_multi_proof_leaf(multi_proof)
        assert not SimpleMerkleTree.verify_multi_proof(tree.root, multi_proof)

    @pytest.mark.parametrize("sort_leaves", (True, False))
    def test_dump_and_load(self, sort_leaves):
        _, tree = make_tree("abcdef", sort_leaves)
        dumped = tree.dump()
        assert dumped.format == "simple-v1"
        assert dumped.hash is None

        tree2 = SimpleMerkleTree.load(dumped)
        tree2.validate()
        assert tree2.tree == tree.tree
        assert tree2.values == tree.values
        assert tree2.root == tree.root

    def test_json_round_trip(self):
        import json

        _, tree = make_tree("abcdef")
        back = SimpleMerkleTree.from_json(json.loads(json.dumps(tree.to_json())))
        assert back.root == tree.root

    def test_equivalent_to_standard_over_leaf_hashes(self):
        "A StandardMerkleTree equals a SimpleMerkleTree over its leaf hashes"
        values = [["a"], ["b"], ["c"], ["d"]]
        std = StandardMerkleTree.of(values, ["string"])
        smp = SimpleMerkleTree.of([standard_leaf_hash(v, ["string"]) for v in values])
        assert smp.root == std.root
        for i, v in enumerate(values):
            assert smp.get_proof(standard_leaf_hash(v, ["string"])) == std.get_proof(i)

    @pytest.mark.parametrize("sort_leaves", (True, False))
    def test_custom_node_hash(self, sort_leaves):
        leaves = [keccak(text=x) for x in "abcdef"]
        tree = SimpleMerkleTree.of(leaves, sort_leaves, node_hash=custom_node_hash)
        tree.validate()

        # a tree with the default node hash must differ from the custom one
        default_tree = SimpleMerkleTree.of(leaves, sort_leaves)
        assert tree.root != default_tree.root

        for index in range(len(leaves)):
            proof = tree.get_proof(index)
            assert tree.verify_leaf(index, proof)
            leaf = tree.values[index].value
            assert SimpleMerkleTree.verify(
                tree.root, leaf, proof, node_hash=custom_node_hash
            )
            # verifying with the wrong (default) node hash must fail
            assert not SimpleMerkleTree.verify(tree.root, leaf, proof)

        mp = tree.get_multi_proof([0, 2, 4])
        assert SimpleMerkleTree.verify_multi_proof(
            tree.root, mp, node_hash=custom_node_hash
        )

    def test_custom_node_hash_dump_load(self):
        leaves = [keccak(text=x) for x in "abcdef"]
        tree = SimpleMerkleTree.of(leaves, node_hash=custom_node_hash)
        dumped = tree.dump()
        assert dumped.hash == "custom"

        reloaded = SimpleMerkleTree.load(dumped, node_hash=custom_node_hash)
        assert reloaded.root == tree.root

    def test_load_custom_data_without_node_hash_fails(self):
        leaves = [keccak(text=x) for x in "abcdef"]
        dumped = SimpleMerkleTree.of(leaves, node_hash=custom_node_hash).dump()
        with pytest.raises(ValueError) as ctx:
            SimpleMerkleTree.load(dumped)
        assert "Data expects a custom node hashing function" in str(ctx.value)

    def test_load_standard_data_with_node_hash_fails(self):
        leaves = [keccak(text=x) for x in "abcdef"]
        dumped = SimpleMerkleTree.of(leaves).dump()
        with pytest.raises(ValueError) as ctx:
            SimpleMerkleTree.load(dumped, node_hash=custom_node_hash)
        assert "Data does not expect a custom node hashing function" in str(ctx.value)

    def test_reject_unrecognized_tree(self):
        with pytest.raises(ValueError) as ctx:
            SimpleMerkleTree.load(
                SimpleMerkleTreeData(tree=[], values=[], format="nonstandard")
            )
        assert "Unknown format 'nonstandard'" in str(ctx.value)

    @pytest.mark.parametrize("sort_leaves", (True, False))
    def test_out_of_bounds(self, sort_leaves):
        _, tree = make_tree("a", sort_leaves)
        with pytest.raises(Exception) as ctx:
            tree.get_proof(1)
        assert "Index out of bounds" in str(ctx.value)

    def test_reject_malformed(self):
        with pytest.raises(Exception) as ctx:
            tree = SimpleMerkleTree.load(
                SimpleMerkleTreeData(
                    format="simple-v1",
                    tree=[ZERO_BYTES],
                    values=[LeafValue(value=keccak(text="a"), tree_index=0)],
                )
            )
            tree.get_proof(0)
        assert "Merkle tree does not contain the expected value" in str(ctx.value)
