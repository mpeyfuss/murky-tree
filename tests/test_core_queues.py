from copy import deepcopy
from itertools import combinations

from murky_tree.core import (
    get_multi_proof,
    make_merkle_tree,
    process_multi_proof,
)


def test_every_selection_and_input_immutability():
    for size in range(1, 9):
        tree = make_merkle_tree([bytes([i]) * 32 for i in range(size)])
        for count in range(size + 1):
            for selection in combinations(range(size - 1, 2 * size - 1), count):
                indices = list(selection)
                original = indices.copy()
                proof = get_multi_proof(tree, indices)
                assert indices == original
                assert proof.leaves == [tree[i] for i in sorted(indices, reverse=True)]
                snapshot = deepcopy(proof)
                assert process_multi_proof(proof) == tree[0]
                assert proof == snapshot
