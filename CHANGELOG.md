# Changelog

## 0.1.1 - UNRELEASED

### Fixes

- CLI: align interrupt handling and subprocess exit normalization, add a `--version` flag, repair the smoke validation script, and enforce the non-interactive `--dry-run` / `--force` safety contract for destructive steps.
- Config: resolve the default Conda path from `%USERPROFILE%` instead of a user-specific absolute path.

### Docs

- Docs: move the main manual into `docs/`, add operator notes for local runs, document the version flag, clarify supported output modes, replace the old CLI reference with an implementation-oriented spec, and tighten the wrapper safety/config ownership guidance.

### Build

- Tooling: add `ruff` and `mypy` checks for `src/` and `tests/`.

## 0.1.0 - 2026-04-15

### Features

- CLI: ship the Windows-first `maya-cython-compile` command for building Maya-targeted Cython packages from a normal Python environment.
- Pipeline: add `doctor`, `create-env`, `build`, `smoke`, `assemble`, and `run` commands with a shared non-interactive `--dry-run` / `--force` workflow.
- Build flow: generate a disposable target build tree under `build/target-build/`, build wheels inside the configured Conda environment, validate them under `mayapy`, and assemble the final Maya module layout under `dist/module/`.
- Config: split tracked build metadata in `build-config.json` from repo-scoped machine overrides in `.maya-cython-compile.json`.
- Scaffold: add the sample `maya_tool` package and the initial Maya 2025 / CPython 3.11 build scaffold.

### Docs

- Docs: rename the project to `maya-cython-compile`, rewrite usage around the CLI workflow, move the reference material into `docs/`, and keep the root `README.md` as a short entrypoint into the documentation set.
