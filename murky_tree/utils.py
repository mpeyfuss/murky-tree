from collections.abc import Callable, Sequence
from typing import Any

from eth_abi.grammar import ABIType, parse
from eth_typing import HexStr, Primitives
from eth_utils import keccak as eth_utils_keccak
from eth_utils import to_bytes


def check_bounds(array: list, index: int) -> None:
    if index < 0 or index >= len(array):
        raise ValueError("Index out of bounds")


def transform_int_leaves(
    value: Any,
    abi_type: str | ABIType,
    on_int: Callable[[int | str], int | str],
) -> Any:
    """Apply ``on_int`` to every uint*/int* leaf of an ABI-typed value.

    Walks the ABI type grammar (via ``eth_abi.grammar``) so integers nested
    inside arrays and tuples/structs are transformed at any depth. Used to
    (de)serialize integers as JSON decimal strings for JavaScript interop: a
    large ``uint256`` as a JSON number would exceed JS's ``Number`` precision.
    """
    node = parse(abi_type) if isinstance(abi_type, str) else abi_type
    if node.is_array:  # peel one array dimension
        return [transform_int_leaves(v, node.item_type, on_int) for v in value]
    components = getattr(node, "components", None)
    if components is not None:  # tuple / struct
        return [
            transform_int_leaves(v, c, on_int)
            for v, c in zip(value, components, strict=True)
        ]
    if getattr(node, "base", None) in ("uint", "int"):  # integer leaf
        return on_int(value)
    return value  # address / string / bool / bytes


def encode_values_for_json(values: Sequence[Any], types: list[str]) -> list:
    """Serialize a sequence of values for JSON, matching @openzeppelin/merkle-tree.

    Integer values are emitted as decimal strings (at any nesting depth) so the
    JSON is loadable by the JS library and survives its Number precision limit.

    The length of `values` must match the length of `types`. Each item in `values` must match the proper string item in `types`.
    """
    return [transform_int_leaves(v, t, str) for v, t in zip(values, types, strict=True)]


def decode_values_from_json(values: Sequence[Any], types: list[str]) -> list:
    """Inverse of ``encode_values_for_json``: decimal strings back to ints.

    The length of `values` must match the length of `types`. Each item in `values` must match the proper string item in `types`.
    """
    return [transform_int_leaves(v, t, int) for v, t in zip(values, types, strict=True)]


def keccak(
    primitive: Primitives | None = None,
    text: str | None = None,
    hexstr: HexStr | None = None,
) -> bytes:
    """Taken from web3py"""
    if isinstance(primitive, (bytes, int, type(None))):
        input_bytes = to_bytes(primitive, hexstr=hexstr, text=text)
        return eth_utils_keccak(input_bytes)

    raise TypeError(
        f"You called keccak with first arg {primitive!r} and keywords "
        f"{{'text': {text!r}, 'hexstr': {hexstr!r}}}. You must call it with "
        "one of these approaches: keccak(text='txt'), keccak(hexstr='0x747874'), "
        "keccak(b'\\x74\\x78\\x74'), or keccak(0x747874)."
    )
