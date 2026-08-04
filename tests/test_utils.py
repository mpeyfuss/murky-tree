import pytest
from eth_abi import encode as abi_encode
from eth_abi.grammar import parse
from eth_utils import to_bytes

from murky_tree.utils import (
    decode_values_from_json,
    encode_values_for_json,
    transform_int_leaves,
)

ADDR = "0x" + "11" * 20
ADDR2 = "0x" + "22" * 20


class TestTransformIntLeaves:
    def test_flat_int_roundtrip(self):
        assert transform_int_leaves(5, "uint256", str) == "5"
        assert transform_int_leaves("5", "uint256", int) == 5

    def test_signed_int(self):
        assert transform_int_leaves(-5, "int256", str) == "-5"
        assert transform_int_leaves("-5", "int256", int) == -5

    def test_big_int_lossless(self):
        big = 2**255 - 1
        as_str = transform_int_leaves(big, "uint256", str)
        assert as_str == str(big)
        assert transform_int_leaves(as_str, "uint256", int) == big

    def test_non_integer_types_pass_through(self):
        assert transform_int_leaves(ADDR, "address", str) == ADDR
        assert transform_int_leaves("hello", "string", str) == "hello"
        assert transform_int_leaves(True, "bool", str) is True
        raw = to_bytes(hexstr="0x" + "ab" * 32)
        assert transform_int_leaves(raw, "bytes32", str) == raw

    def test_dynamic_array(self):
        assert transform_int_leaves([1, 2, 3], "uint256[]", str) == ["1", "2", "3"]
        assert transform_int_leaves([], "uint256[]", str) == []

    def test_fixed_array(self):
        assert transform_int_leaves([ADDR, ADDR2], "address[2]", str) == [ADDR, ADDR2]
        assert transform_int_leaves([1, 2], "uint8[2]", str) == ["1", "2"]

    def test_tuple_struct_normalizes_to_list(self):
        # a struct value may come in as a tuple; the result is always a list
        assert transform_int_leaves((ADDR, 5), "(address,uint256)", str) == [ADDR, "5"]

    def test_deeply_nested(self):
        value = (2, (ADDR2, [10**20, 7]))
        expected = ["2", [ADDR2, ["100000000000000000000", "7"]]]
        result = transform_int_leaves(value, "(uint8,(address,uint256[]))", str)
        assert result == expected

    def test_accepts_already_parsed_node(self):
        # the recursion passes ABIType nodes, not strings -- both must work
        assert transform_int_leaves(5, parse("uint256"), str) == "5"


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
        [["(address,uint256)", [ADDR, 5 * 10**18]], ["uint256[]", [10**19, 2]]],
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
