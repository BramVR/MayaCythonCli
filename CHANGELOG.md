# Changelog

## 0.1.1 - UNRELEASED

### Features

- Verification: add the `verify` command with agent-facing `target-dry-run`, `target-run`, and `installed-cli-config-show` scenarios plus per-run repro bundles under `build/agent-runs/`.

### Fixes

- CLI: align interrupt handling and subprocess exit normalization, add a `--version` flag, repair the smoke validation script, and enforce the non-interactive `--dry-run` / `--force` safety contract for destructive steps.
- CLI: add opt-in `--json-errors` failure payloads for agent retry loops and fix wheel artifact metadata so built packages carry the target fields later validation requires.
- Assembly: make assembled Maya module outputs target-owned so different target builds do not clobber one another.
- Config: resolve the default Conda path from `%USERPROFILE%` instead of a user-specific absolute path.

### Docs

- Docs: move the main manual into `docs/`, add operator notes for local runs, document the version flag, clarify supported output modes, replace the old CLI reference with an implementation-oriented spec, and tighten the wrapper safety/config ownership guidance.
- Docs: document the `verify` workflow, the structured error contract, and the recommended agent repair loop in the CLI and testing guides.

### Build

- Tooling: add `ruff` and `mypy` checks for `src/` and `tests/`.
- Build flow: harden target artifact selection so `build`, `smoke`, and `assemble` validate the manifest-selected wheel instead of loosely consuming whichever matching wheel name was newest.

## 0.1.0 - 2026-04-15

### Features

- CLI: ship the Windows-first `maya-cython-compile` command for building Maya-targeted Cython packages from a normal Python environment.
- Pipeline: add `doctor`, `create-env`, `build`, `smoke`, `assemble`, and `run` commands with a shared non-interactive `--dry-run` / `--force` workflow.
- Build flow: generate a disposable target build tree under `build/target-build/`, build wheels inside the configured Conda environment, validate them under `mayapy`, and assemble the final Maya module layout under `dist/module/`.
- Config: split tracked build metadata in `build-config.json` from repo-scoped machine overrides in `.maya-cython-compile.json`.
- Scaffold: add the sample `maya_tool` package and the initial Maya 2025 / CPython 3.11 build scaffold.

### Docs

- Docs: rename the project to `maya-cython-compile`, rewrite usage around the CLI workflow, move the reference material into `docs/`, and keep the root `README.md` as a short entrypoint into the documentation set.
