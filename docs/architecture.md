---
summary: "CLI ownership, package split, and how the wheel-to-module pipeline is structured."
read_when:
  - "When changing the pipeline shape or build-tree layout."
  - "When moving logic between Python and PowerShell."
---

# Architecture

The repo treats `maya-cython-compile` as the product. The Maya package is input to that CLI, not the package that owns the orchestration logic.

## Package split

- [../src/maya_cython_compile](../src/maya_cython_compile) - CLI entrypoint, config resolution, and pipeline orchestration
- [../src/maya_tool](../src/maya_tool) - sample Maya package compiled by the pipeline

That split avoids coupling the builder and the thing being built into one artifact.

## Source of truth

Tracked build metadata lives in [../build-config.json](../build-config.json).

It can be expressed either as:

- a legacy flat single-target config
- a named-target config with shared top-level build fields plus `default_target` and `targets`

The resolved target defines:

- distribution name
- package name and package directory
- module name and Maya version
- package version
- compiled modules
- package data
- smoke settings
- target platform for Maya module assembly

Local machine paths are resolved separately through CLI flags, environment variables, repo-local config, and built-in defaults. See [config.md](config.md).

## Pipeline ownership

The real build flow lives in [../src/maya_cython_compile/pipeline.py](../src/maya_cython_compile/pipeline.py).

It owns:

- target selection
- Conda and `mayapy` validation
- Maya include and import-lib discovery
- build env creation
- destructive cleanup planning through the shared `--dry-run` and `--force` contract
- temporary target tree generation
- wheel build execution
- smoke validation under `mayapy`
- Maya module assembly

PowerShell wrappers under [../scripts](../scripts) are compatibility entrypoints only.

## Temporary build tree

Wheel builds do not run from the tracked source tree directly. The CLI prepares a disposable build root under `build/target-build/<target>/` through [../src/maya_cython_compile/target_builder.py](../src/maya_cython_compile/target_builder.py).

That keeps packaging logic isolated while still generating target-specific build files.

## Target-scoped outputs

The pipeline now namespaces mutable outputs by selected target so different Maya and platform builds do not clobber one another:

- build temp files: `build/tmp/<target>/`
- built wheels: `dist/<target>/`
- smoke extraction: `build/smoke/<target>/wheel/`
- assembled module payloads: `dist/module/<target>/<ModuleName>/`

## Runtime split

The pipeline separates build-time Python from Maya runtime validation:

- Conda env - used for `Cython`, `setuptools`, and wheel creation
- `mayapy` - used for Maya ABI discovery and runtime smoke validation

This lets the repo run from a normal Python environment without making `mayapy` the primary tool runner.

## Assembly model

The wheel is the intermediate artifact. The final Maya module payload is assembled into:

- `dist/module/<target>/<ModuleName>/contents/scripts/`
- `dist/module/<target>/<ModuleName>/<ModuleName>.mod`

Assembly skips wheel metadata directories ending in `.dist-info` and `.data`, and the `.mod` file's `PLATFORM:` token is derived from the selected target platform instead of being hardcoded to Windows.
