import pytest
from eth_abi import encode as abi_encode
from eth_abi.grammar import parse
from eth_utils import to_bytes, to_hex

from murky_tree.utils import (
    decode_values_from_json,
    encode_values_for_json,
    transform_leaves,
)

ADDR = "0x" + "11" * 20
ADDR2 = "0x" + "22" * 20


class TestTransformLeaves:
    def test_flat_int_roundtrip(self):
        assert transform_leaves(5, "uint256", "to-json") == "5"
        assert transform_leaves("5", "uint256", "from-json") == 5

    def test_signed_int(self):
        assert transform_leaves(-5, "int256", "to-json") == "-5"
        assert transform_leaves("-5", "int256", "from-json") == -5

    def test_big_int_lossless(self):
        big = 2**255 - 1
        as_str = transform_leaves(big, "uint256", "to-json")
        assert as_str == str(big)
        assert transform_leaves(as_str, "uint256", "from-json") == big

    def test_bytes_roundtrip(self):
        raw = to_bytes(hexstr="0x" + "ab" * 32)
        as_hex = transform_leaves(raw, "bytes32", "to-json")
        assert as_hex == to_hex(raw)
        assert transform_leaves(as_hex, "bytes32", "from-json") == raw

    def test_dynamic_bytes_roundtrip(self):
        raw = to_bytes(hexstr="0xdeadbeef")
        as_hex = transform_leaves(raw, "bytes", "to-json")
        assert as_hex == to_hex(raw)
        assert transform_leaves(as_hex, "bytes", "from-json") == raw

    def test_non_transformed_types_pass_through(self):
        assert transform_leaves(ADDR, "address", "to-json") == ADDR
        assert transform_leaves("hello", "string", "to-json") == "hello"
        assert transform_leaves(True, "bool", "to-json") is True

    def test_dynamic_array(self):
        assert transform_leaves([1, 2, 3], "uint256[]", "to-json") == ["1", "2", "3"]
        assert transform_leaves([], "uint256[]", "to-json") == []

    def test_fixed_array(self):
        assert transform_leaves([ADDR, ADDR2], "address[2]", "to-json") == [ADDR, ADDR2]
        assert transform_leaves([1, 2], "uint8[2]", "to-json") == ["1", "2"]

    def test_tuple_struct_normalizes_to_list(self):
        # a struct value may come in as a tuple; the result is always a list
        assert transform_leaves((ADDR, 5), "(address,uint256)", "to-json") == [
            ADDR,
            "5",
        ]

    def test_deeply_nested(self):
        value = (2, (ADDR2, [10**20, 7]))
        expected = ["2", [ADDR2, ["100000000000000000000", "7"]]]
        result = transform_leaves(value, "(uint8,(address,uint256[]))", "to-json")
        assert result == expected

    def test_accepts_already_parsed_node(self):
        # the recursion passes ABIType nodes, not strings -- both must work
        assert transform_leaves(5, parse("uint256"), "to-json") == "5"


class TestEncodeDecodeValues:
    def test_stringifies_all_ints_at_any_depth(self):
        types = ["(address,uint256)", "uint256[]"]
        values = [(ADDR, 5 * 10**18), [10**19, 2]]
        assert encode_values_for_json(values, types) == [
            [ADDR, "5000000000000000000"],
            ["10000000000000000000", "2"],
        ]

    @pytest.mark.parametrize(
        ["abi_str", "abi_items"],
        [
            ["(address,uint256)", [ADDR, 5 * 10**18]],
            ["uint256[]", [10**19, 2]],
            ["(address,bytes32)", [ADDR, to_bytes(hexstr="0x" + "cd" * 32)]],
        ],
    )
    def test_roundtrip_is_abi_equivalent(self, abi_str, abi_items):
        types = [abi_str]
        values = [abi_items]
        decoded = decode_values_from_json(encode_values_for_json(values, types), types)
        # lossless: decoded values re-encode to identical ABI bytes
        assert abi_encode(types, decoded) == abi_encode(types, values)

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            encode_values_for_json([1], ["uint256", "uint256"])
