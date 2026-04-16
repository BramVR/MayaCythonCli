# Architecture

Date: 2026-04-15

## Why This Repo Is a CLI

This repo used to lean on ad-hoc PowerShell scripts and a top-level build script. That shape was weak for three reasons:

- the install story was not the same thing as the build story
- Maya-specific build requirements leaked into the top-level package boundary
- the pipeline steps were harder to test and harder to reuse from one command surface

The repo now treats the build pipeline as an installable CLI. The CLI is the product. The Maya package is build input.

## Package Split

The split is intentional:

- [../src/maya_cython_compile](../src/maya_cython_compile): orchestration CLI
- [../src/maya_tool](../src/maya_tool): sample Maya package compiled by the pipeline

This avoids a bad coupling where the builder and the thing being built are packaged as the same artifact.

## Source of Truth

Tracked build metadata lives in [../build-config.json](../build-config.json).

It defines:

- distribution name
- package name
- package directory
- module name
- Maya version
- package version
- compiled modules
- package data
- smoke-test settings

Local machine-specific paths are resolved separately through:

- CLI flags
- environment variables
- `.maya-cython-compile.json`
- built-in defaults

That split keeps repo configuration portable while still letting each machine override local tools and paths.

The local config layer is intentionally repo-scoped: the default file is `<repo-root>/.maya-cython-compile.json`, unless `--config` points to a different file. There is no user-level or system-level config discovery in the current implementation.

## Pipeline Ownership

The CLI owns the real pipeline logic in [../src/maya_cython_compile/pipeline.py](../src/maya_cython_compile/pipeline.py).

That module is responsible for:

- validating Conda and `mayapy`
- discovering Maya headers and import libs
- creating the build env
- planning destructive cleanup and enforcing the shared `--dry-run` / `--force` contract
- preparing the temporary target build tree
- building the wheel
- validating the wheel under `mayapy`
- assembling the Maya module payload

PowerShell is now a compatibility edge, not the source of truth. The wrappers in [../scripts](../scripts) only delegate into the CLI.

## Temporary Build Tree

The tracked repo root is not used directly as the wheel build root. Instead, the CLI generates a disposable target build tree under:

- `build/target-build/`

That build tree is prepared by [../src/maya_cython_compile/target_builder.py](../src/maya_cython_compile/target_builder.py).

This keeps the CLI packaging boundary clean while still generating a target-specific `setup.py` for the compiled wheel build.

## Runtime Split

The pipeline intentionally separates build-time Python from runtime validation:

- Conda env: used for `Cython`, `setuptools`, and wheel creation
- `mayapy`: used only for runtime validation and Maya ABI discovery

That split matters because the repo should be operable from a normal Python environment without turning `mayapy` into the primary tool runner.

## Assembly Model

The wheel is the intermediate artifact.

The final Maya deployment layout is assembled from that wheel into:

- `dist/module/<ModuleName>/contents/scripts/`
- `dist/module/<ModuleName>/<ModuleName>.mod`

Assembly skips wheel metadata directories because they do not belong in the Maya module payload.

## Why This Shape Was Chosen

This structure follows the useful parts of the Steipete CLI examples that informed the redesign:

- thin entrypoint
- real logic in modules
- clear config resolution
- one command surface for humans and automation
- compatibility wrappers at the edge instead of shell scripts owning business logic

The result is easier to reason about, easier to document, and easier to grow once the scaffold package is replaced with a real tool.
