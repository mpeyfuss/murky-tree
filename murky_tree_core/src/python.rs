use crate::{Node, Result};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyList};

fn error<T>(value: Result<T>) -> PyResult<T> {
    value.map_err(PyValueError::new_err)
}

fn node(value: &[u8]) -> PyResult<Node> {
    value
        .try_into()
        .map_err(|_| PyValueError::new_err("Merkle tree nodes must be byte array of length 32"))
}

fn nodes(values: &Bound<'_, PyList>) -> PyResult<Vec<Node>> {
    values
        .iter()
        .map(|v| node(v.cast::<PyBytes>()?.as_bytes()))
        .collect()
}

fn output<'py>(py: Python<'py>, values: Vec<Node>) -> PyResult<Bound<'py, PyList>> {
    PyList::new(py, values.iter().map(|v| PyBytes::new(py, v)))
}

#[pyfunction]
fn keccak<'py>(py: Python<'py>, data: &[u8]) -> Bound<'py, PyBytes> {
    PyBytes::new(py, &crate::keccak(data))
}

#[pyfunction]
fn double_keccak<'py>(py: Python<'py>, data: &[u8]) -> Bound<'py, PyBytes> {
    PyBytes::new(py, &crate::keccak(&crate::keccak(data)))
}

#[pyfunction]
fn make_merkle_tree<'py>(
    py: Python<'py>,
    leaves: &Bound<'py, PyList>,
) -> PyResult<Bound<'py, PyList>> {
    let leaves = nodes(leaves)?;
    let tree = error(py.detach(|| crate::make_merkle_tree(&leaves)))?;
    output(py, tree)
}

#[pyfunction]
fn process_proof<'py>(
    py: Python<'py>,
    leaf: &[u8],
    proof: &Bound<'py, PyList>,
) -> PyResult<Bound<'py, PyBytes>> {
    let leaf = node(leaf)?;
    let proof = nodes(proof)?;
    Ok(PyBytes::new(py, &crate::process_proof(leaf, &proof)))
}

#[pyfunction]
fn process_multi_proof<'py>(
    py: Python<'py>,
    leaves: &Bound<'py, PyList>,
    proof: &Bound<'py, PyList>,
    flags: Vec<bool>,
) -> PyResult<Bound<'py, PyBytes>> {
    let leaves = nodes(leaves)?;
    let proof = nodes(proof)?;
    let root = error(py.detach(|| crate::process_multi_proof(&leaves, &proof, &flags)))?;
    Ok(PyBytes::new(py, &root))
}

#[pyfunction]
fn is_valid_merkle_tree(py: Python<'_>, tree: &Bound<'_, PyList>) -> PyResult<bool> {
    let tree = match nodes(tree) {
        Ok(tree) => tree,
        Err(e) if e.is_instance_of::<PyValueError>(py) => return Ok(false),
        Err(e) => return Err(e),
    };
    Ok(py.detach(|| crate::is_valid_merkle_tree(&tree)))
}

#[pyfunction]
fn proof_indices(size: usize, index: usize) -> PyResult<Vec<usize>> {
    error(crate::proof_indices(size, index))
}

#[pyfunction]
fn multi_proof_indices(
    size: usize,
    indices: Vec<usize>,
) -> PyResult<(Vec<usize>, Vec<usize>, Vec<bool>)> {
    let mp = error(crate::multi_proof_indices(size, indices))?;
    Ok((mp.leaves, mp.proof, mp.flags))
}

#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(keccak, m)?)?;
    m.add_function(wrap_pyfunction!(double_keccak, m)?)?;
    m.add_function(wrap_pyfunction!(make_merkle_tree, m)?)?;
    m.add_function(wrap_pyfunction!(process_proof, m)?)?;
    m.add_function(wrap_pyfunction!(process_multi_proof, m)?)?;
    m.add_function(wrap_pyfunction!(is_valid_merkle_tree, m)?)?;
    m.add_function(wrap_pyfunction!(proof_indices, m)?)?;
    m.add_function(wrap_pyfunction!(multi_proof_indices, m)?)?;
    Ok(())
}
