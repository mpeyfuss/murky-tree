// Generates cross-implementation test vectors using the *original*
// @openzeppelin/merkle-tree JS library. The Python port (murky-tree) is tested
// against this output (see tests/test_reference_vectors.py) so that "compatible
// with the JS library" is verified rather than assumed.
//
// Run with: bun run generate  (writes vectors.json next to this file)

import { SimpleMerkleTree, StandardMerkleTree } from "@openzeppelin/merkle-tree";
import {
  keccak256,
  standardNodeHash,
  type NodeHash,
} from "@openzeppelin/merkle-tree/dist/hashes";
import ozPkg from "@openzeppelin/merkle-tree/package.json" with { type: "json" };

// keccak256 over the UTF-8 bytes of a string (the library's keccak256 treats a
// bare string as a hex-encoded byte array, so text must be encoded first).
const keccakText = (s: string): string =>
  keccak256(new TextEncoder().encode(s));

// A custom, non-default node hash: double-hash the sorted pair. This mirrors
// tests/test_simple.py's `custom_node_hash` exactly -- standardNodeHash already
// does keccak256(sorted(a,b)), so one more keccak256 gives keccak(keccak(lo+hi)).
const customNodeHash: NodeHash = (a, b) => keccak256(standardNodeHash(a, b));

// Index subsets used for multiproofs -- the same sets the existing
// self-referential Python tests exercise. For trees with fewer than 6 leaves the
// sets are clamped to valid indices and de-duplicated.
const CANONICAL_MULTIPROOF_SETS = [[], [0, 1], [0, 1, 5], [1, 3, 4, 5], [0, 2, 4, 5], [0, 1, 2, 3, 4, 5]];

function multiproofSets(leafCount: number): number[][] {
  const seen = new Set<string>();
  const sets: number[][] = [];
  for (const set of CANONICAL_MULTIPROOF_SETS) {
    const clamped = set.filter((i) => i < leafCount);
    const key = clamped.join(",");
    if (!seen.has(key)) {
      seen.add(key);
      sets.push(clamped);
    }
  }
  return sets;
}

type MerkleTreeLike = {
  root: string;
  dump(): { tree: string[] } & Record<string, unknown>;
  leafHash(leaf: any): string;
  getProof(leaf: number | any): string[];
  getMultiProof(leaves: (number | any)[]): {
    leaves: any[];
    proof: string[];
    proofFlags: boolean[];
  };
};

function buildCase(
  name: string,
  type: "standard" | "simple",
  input: Record<string, unknown>,
  values: any[],
  tree: MerkleTreeLike,
) {
  return {
    name,
    type,
    input,
    root: tree.root,
    tree: tree.dump().tree,
    leafHashes: values.map((v) => tree.leafHash(v)),
    proofs: values.map((_, i) => tree.getProof(i)),
    multiProofs: multiproofSets(values.length).map((indices) => {
      const mp = tree.getMultiProof(indices);
      return {
        indices,
        leaves: mp.leaves,
        proof: mp.proof,
        proofFlags: mp.proofFlags,
      };
    }),
    // The raw JS dump -- the interop oracle the Python to_json()/from_json()
    // must match byte-for-byte (as parsed JSON).
    dump: tree.dump(),
  };
}

function standardCase(
  name: string,
  leafEncoding: string[],
  sortLeaves: boolean,
  values: any[][],
) {
  const tree = StandardMerkleTree.of(values, leafEncoding, { sortLeaves });
  return buildCase(
    name,
    "standard",
    { leafEncoding, sortLeaves, nodeHash: "default", values },
    values,
    tree,
  );
}

function simpleCase(
  name: string,
  sortLeaves: boolean,
  values: string[],
  custom: boolean,
) {
  const tree = SimpleMerkleTree.of(values, {
    sortLeaves,
    ...(custom ? { nodeHash: customNodeHash } : {}),
  });
  return buildCase(
    name,
    "simple",
    { sortLeaves, nodeHash: custom ? "custom" : "default", values },
    values,
    tree,
  );
}

// Standard-tree leaves: "abcdef" mirrors the existing Python tests so hashes
// can be cross-checked against known values.
const STRING_VALUES = [..."abcdef"].map((c) => [c]);

// A realistic airdrop-style tree. uint256 amounts are decimal *strings* so the
// vectors stay JSON-safe (no bigint) and both libraries agree on the value.
const AIRDROP_VALUES = [
  ["0x1111111111111111111111111111111111111111", "5000000000000000000"],
  ["0x2222222222222222222222222222222222222222", "2500000000000000000"],
  ["0x3333333333333333333333333333333333333333", "1000000000000000000"],
  ["0x4444444444444444444444444444444444444444", "0"],
];

// Nested/complex ABI types: a struct leaf plus a dynamic array of big uints.
// Integers (including nested ones) are passed as decimal strings -- the only
// JS-safe JSON form for values beyond Number's precision -- so the vectors
// exercise recursive integer <-> string (de)serialization.
const NESTED_ENCODING = ["(address,uint256)", "uint256[]"];
const NESTED_VALUES = [
  [["0x1111111111111111111111111111111111111111", "5000000000000000000"], ["1", "2", "3"]],
  [["0x2222222222222222222222222222222222222222", "2500000000000000000"], ["10000000000000000000"]],
  [["0x3333333333333333333333333333333333333333", "0"], []],
];

// Simple-tree leaves: already-hashed bytes32 values.
const SIMPLE_LEAVES = [..."abcdef"].map(keccakText);

const vectors = {
  generator: "@openzeppelin/merkle-tree",
  version: ozPkg.version,
  cases: [
    standardCase("standard-string-sorted", ["string"], true, STRING_VALUES),
    standardCase("standard-string-unsorted", ["string"], false, STRING_VALUES),
    standardCase("standard-airdrop-sorted", ["address", "uint256"], true, AIRDROP_VALUES),
    standardCase("standard-airdrop-unsorted", ["address", "uint256"], false, AIRDROP_VALUES),
    standardCase("standard-nested-sorted", NESTED_ENCODING, true, NESTED_VALUES),
    simpleCase("simple-sorted", true, SIMPLE_LEAVES, false),
    simpleCase("simple-unsorted", false, SIMPLE_LEAVES, false),
    simpleCase("simple-custom-hash", true, SIMPLE_LEAVES, true),
  ],
};

const outPath = new URL("./vectors.json", import.meta.url);
await Bun.write(outPath, JSON.stringify(vectors, null, 2) + "\n");
console.log(`Wrote ${vectors.cases.length} cases to ${outPath.pathname}`);
