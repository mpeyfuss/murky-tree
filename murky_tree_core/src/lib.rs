//! Ethereum Keccak Merkle trees with OpenZeppelin's flat heap layout.
//! Python-independent API; enable `python` for the PyO3 adapter.
use std::collections::VecDeque;
use tiny_keccak::{Hasher, Keccak};

pub type Node = [u8; 32];
pub type Result<T> = std::result::Result<T, &'static str>;

pub fn keccak(data: &[u8]) -> Node {
    let mut hash = Keccak::v256();
    hash.update(data);
    let mut out = [0; 32];
    hash.finalize(&mut out);
    out
}

pub fn hash_pair(a: &Node, b: &Node) -> Node {
    let (lo, hi) = if a < b { (a, b) } else { (b, a) };
    let mut input = [0; 64];
    input[..32].copy_from_slice(lo);
    input[32..].copy_from_slice(hi);
    keccak(&input)
}

pub fn make_merkle_tree(leaves: &[Node]) -> Result<Vec<Node>> {
    if leaves.is_empty() {
        return Err("Expected non-zero number of leaves");
    }
    let size = leaves
        .len()
        .checked_mul(2)
        .and_then(|n| n.checked_sub(1))
        .ok_or("Tree is too large")?;
    let mut tree = vec![[0; 32]; size];
    for (i, leaf) in leaves.iter().enumerate() {
        tree[size - 1 - i] = *leaf;
    }
    for i in (0..leaves.len() - 1).rev() {
        tree[i] = hash_pair(&tree[2 * i + 1], &tree[2 * i + 2]);
    }
    Ok(tree)
}

fn check_leaf(size: usize, index: usize) -> Result<()> {
    if index >= size || index < size / 2 {
        return Err("Index is not a leaf");
    }
    Ok(())
}

fn sibling(i: usize) -> usize {
    if i % 2 == 0 {
        i - 1
    } else {
        i + 1
    }
}

/// Return positions, so a Python caller need only read O(log n) nodes.
pub fn proof_indices(size: usize, mut index: usize) -> Result<Vec<usize>> {
    check_leaf(size, index)?;
    let mut proof = Vec::new();
    while index > 0 {
        let s = sibling(index);
        if s >= size {
            return Err("Index is not in tree");
        }
        proof.push(s);
        index = (index - 1) / 2;
    }
    Ok(proof)
}

pub fn process_proof(leaf: Node, proof: &[Node]) -> Node {
    proof.iter().fold(leaf, |a, b| hash_pair(&a, b))
}

#[derive(Debug, PartialEq, Eq)]
pub struct MultiProofIndices {
    pub leaves: Vec<usize>,
    pub proof: Vec<usize>,
    pub flags: Vec<bool>,
}

pub fn multi_proof_indices(size: usize, mut indices: Vec<usize>) -> Result<MultiProofIndices> {
    for &i in &indices {
        check_leaf(size, i)?;
    }
    indices.sort_unstable_by(|a, b| b.cmp(a));
    if indices.windows(2).any(|w| w[0] == w[1]) {
        return Err("Cannot prove duplicated index");
    }
    if size == 0 {
        return Err("Index is not in tree");
    }
    let mut queue: VecDeque<_> = indices.iter().copied().collect();
    let mut proof = Vec::new();
    let mut flags = Vec::new();
    while queue.front().is_some_and(|&i| i > 0) {
        let j = queue.pop_front().unwrap();
        let s = sibling(j);
        if s >= size {
            return Err("Index is not in tree");
        }
        if queue.front() == Some(&s) {
            flags.push(true);
            queue.pop_front();
        } else {
            flags.push(false);
            proof.push(s);
        }
        queue.push_back((j - 1) / 2);
    }
    if indices.is_empty() {
        proof.push(0);
    }
    Ok(MultiProofIndices {
        leaves: indices,
        proof,
        flags,
    })
}

pub fn process_multi_proof(leaves: &[Node], proof: &[Node], flags: &[bool]) -> Result<Node> {
    if proof.len() < flags.iter().filter(|&&f| !f).count() {
        return Err("Invalid multiproof format");
    }
    if leaves.len() + proof.len() != flags.len() + 1 {
        return Err("Provided leaves and multiproof are not compatible");
    }
    let mut queue: VecDeque<_> = leaves.iter().copied().collect();
    let mut remaining = proof.iter();
    for &flag in flags {
        let a = queue.pop_front().ok_or("Invalid multiproof format")?;
        let b = if flag {
            queue.pop_front()
        } else {
            remaining.next().copied()
        }
        .ok_or("Invalid multiproof format")?;
        queue.push_back(hash_pair(&a, &b));
    }
    queue
        .pop_front()
        .or_else(|| remaining.next().copied())
        .ok_or("Invalid multiproof format")
}

pub fn is_valid_merkle_tree(tree: &[Node]) -> bool {
    if tree.is_empty() || tree.len() % 2 == 0 {
        return false;
    }
    (0..tree.len() / 2).all(|i| tree[i] == hash_pair(&tree[2 * i + 1], &tree[2 * i + 2]))
}

#[cfg(feature = "python")]
mod python;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ethereum_keccak_vector() {
        assert_eq!(
            keccak(b""),
            [
                0xc5, 0xd2, 0x46, 0x01, 0x86, 0xf7, 0x23, 0x3c, 0x92, 0x7e, 0x7d, 0xb2, 0xdc, 0xc7,
                0x03, 0xc0, 0xe5, 0x00, 0xb6, 0x53, 0xca, 0x82, 0x27, 0x3b, 0x7b, 0xfa, 0xd8, 0x04,
                0x5d, 0x85, 0xa4, 0x70
            ]
        );
    }

    #[test]
    fn all_small_subsets() {
        for n in 1..=9 {
            let leaves: Vec<_> = (0..n).map(|i| keccak(&[i as u8])).collect();
            let tree = make_merkle_tree(&leaves).unwrap();
            assert!(is_valid_merkle_tree(&tree));
            for mask in 0..1 << n {
                let indices = (0..n)
                    .filter(|i| mask & (1 << i) != 0)
                    .map(|i| n - 1 + i)
                    .collect();
                let mp = multi_proof_indices(tree.len(), indices).unwrap();
                let selected: Vec<_> = mp.leaves.iter().map(|&i| tree[i]).collect();
                let proof: Vec<_> = mp.proof.iter().map(|&i| tree[i]).collect();
                assert_eq!(
                    process_multi_proof(&selected, &proof, &mp.flags),
                    Ok(tree[0])
                );
            }
            for i in n - 1..tree.len() {
                let proof: Vec<_> = proof_indices(tree.len(), i)
                    .unwrap()
                    .iter()
                    .map(|&j| tree[j])
                    .collect();
                assert_eq!(process_proof(tree[i], &proof), tree[0]);
            }
        }
    }

    #[test]
    fn invalid_inputs() {
        assert!(make_merkle_tree(&[]).is_err());
        assert!(proof_indices(0, 0).is_err());
        assert!(proof_indices(4, 3).is_err());
        assert!(multi_proof_indices(3, vec![1, 1]).is_err());
        assert!(process_multi_proof(&[], &[[0; 32], [0; 32]], &[true]).is_err());
        assert!(!is_valid_merkle_tree(&[[0; 32], [0; 32]]));
    }
}
