# Releasing murky-tree

Publishing a stable GitHub Release starts `.github/workflows/release.yaml`:

1. Check that the tag is `vX.Y.Z` and matches the version in both Cargo files.
2. Run Rust tests and build/test a wheel for every platform in the Wheels
   workflow matrix, plus the source distribution, using the same reusable
   workflow as ordinary wheel CI.
3. Check distribution metadata and collect the tested files into the
   `pypi-distributions` artifact. The workflow summary lists the version, commit,
   platforms, filenames, and SHA-256 hashes for review.
4. Wait for approval of the **pypi** environment.
5. Publish those exact files through PyPI Trusted Publishing. The publishing job
   does not rebuild the package and uses no stored PyPI API token.

Draft releases and prereleases do not publish. Pushing a tag alone does not
publish either. Ordinary CI and manually running the Wheels workflow only
produce test artifacts. CI and Wheels run on branch pushes and pull requests,
not on tag pushes, so a release builds each wheel once.

## Adding a platform

Add an entry with a unique `name` and its GitHub `runner` to the `include` list
in `.github/workflows/wheels.yaml`. The release workflow picks it up
automatically; no count or list in `release.yaml` needs updating. The build
steps test each wheel on its own runner, so a new entry needs a runner that can
run the wheel natively. Cross-compiled targets (for example musllinux or
Windows arm64 built on an x86-64 runner) also need a `target` passed to
`maturin-action` and a different way to test the wheel.

## One-time GitHub setup

In **mpeyfuss/murky-tree → Settings → Environments**, create an environment named
**`pypi`**:

- Enable **Required reviewers** and add your GitHub account (or a release team).
- Leave **Prevent self-review** disabled if you want to publish the GitHub
  Release and approve its deployment yourself.
- Disable administrator bypass of protection rules if that option is available.
- Under deployment branches/tags, select allowed tags and add **`v*`**.

The workflow's `environment: pypi` declaration does **not** configure required
reviewers. Set them before publishing your first GitHub Release; otherwise
GitHub will not pause for the second confirmation. Required-reviewer support
also depends on the repository visibility and GitHub plan.

## One-time PyPI setup

For the existing `murky-tree` project, open its **Publishing** settings on PyPI
and add a **GitHub** trusted publisher with these fields:

| Field | Value |
| --- | --- |
| Owner | `mpeyfuss` |
| Repository | `murky-tree` |
| Workflow filename | `release.yaml` |
| Environment | `pypi` |

The workflow filename is the publishing workflow, **not** `wheels.yaml` and not
a full path. No PyPI token or GitHub Actions secret is needed. If the project
has not been created on PyPI yet, configure the same fields as a pending
publisher instead.

## Each release

1. In a PR, update the version in `murky_tree_core/Cargo.toml`. Run `cargo check`
   from `murky_tree_core/` to update that package's entry in `Cargo.lock`, and
   commit both files. The Python package version is read from Cargo automatically.
2. Merge after CI passes. Include the workflows and all Rust/Python package files
   in the commit you intend to release.
3. On GitHub's **Releases** page, create a release with a matching tag such as
   **`v2.0.0`**, targeting that exact commit. Write the release notes and click
   **Publish release**. Do not mark it as a prerelease.
4. Open the **Release** workflow run. Wait for validation, builds, and tests to
   finish. Review the distribution summary and the `pypi-distributions` artifact.
5. Click **Review deployments**, select **pypi**, and approve. This is the second
   confirmation and the point at which PyPI publication is authorized.
6. Confirm the version and files appear on PyPI.

The GitHub Release is public during the build and approval period, before the
package appears on PyPI. Reject the deployment if the artifacts are not ready.
Do not move a released tag or reuse a published PyPI version. If an upload fails,
inspect the run and PyPI before retrying: some files may already have been
published, and PyPI will not overwrite them.

This workflow publishes stable `X.Y.Z` releases only. Add an explicit prerelease
policy before using Cargo prerelease versions or GitHub prereleases for PyPI.
