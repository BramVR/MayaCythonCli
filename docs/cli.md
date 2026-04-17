---
summary: "CLI commands, global flags, output modes, and failure codes."
read_when:
  - "When changing command-line behavior or adding flags."
  - "When updating JSON or text output contracts."
---

# CLI

`maya-cython-compile` is a non-interactive CLI for building Maya-compatible Cython wheels, validating them under `mayapy`, and assembling Maya module payloads for an explicit named target.

## Usage

```text
maya-cython-compile
  [--repo-root PATH]
  [--config PATH]
  [--target NAME]
  [--json]
  [--verbose]
  [--conda-exe PATH]
  [--env-path PATH]
  [--maya-py PATH]
  (
    --version
    | config show
    | doctor
    | create-env [--dry-run] [--force]
    | build [--dry-run] [--force]
    | smoke [--dry-run] [--force]
    | assemble [--dry-run] [--force] [--module-name NAME] [--maya-version VERSION]
    | run [--dry-run] [--force] [--ensure-env] [--skip-smoke] [--skip-assemble]
          [--module-name NAME] [--maya-version VERSION]
  )
```

Global flags are accepted before or after the subcommand.

## Global flags

| Flag | Meaning |
| --- | --- |
| `--repo-root PATH` | base directory for config lookup, inputs, and outputs |
| `--config PATH` | alternate repo-local config file |
| `--target NAME` | select a named build target |
| `--json` | emit JSON to stdout |
| `--verbose` | print spawned subprocess commands to stderr |
| `--conda-exe PATH` | override Conda executable or command |
| `--env-path PATH` | override build env location |
| `--maya-py PATH` | override `mayapy` path |
| `--version` | print version and exit |

Flags that are not implemented:

- `--plain`
- `--quiet`

## Commands

### `config show`

Prints the fully resolved config from tracked build metadata, local config, environment variables, and CLI overrides. The payload includes the selected `target`, `available_targets`, the resolved target `platform`, and the target `python_version` used for Conda env creation.

### `doctor`

Checks whether the selected target's Conda executable, env path, and `mayapy` path exist, then runs a target-aware `mayapy` probe that reports runtime platform, Python version, include path, and Python library metadata from `sysconfig`. The checks include both platform and Python-version matches against the selected target.

### `create-env`

Creates the selected target's Conda build environment from [../environment.yml](../environment.yml). The CLI writes a target-scoped environment file under `build/tmp/<target>/conda-environment.yml`, rewrites its `python=` dependency to the resolved target `python_version`, and then runs Conda against that file. If the selected target's env already exists, the command treats that as a replace operation and requires `--force`.

### `build`

Builds the selected target's wheel inside the resolved Conda env. It validates the `mayapy` probe, rejects a target platform or Python-version mismatch, cleans prior build outputs when allowed, prepares `build/target-build/<target>/`, and writes the newest wheel to `dist/<target>/`.

### `smoke`

Finds the newest matching wheel in `dist/<target>/`, extracts it to `build/smoke/<target>/wheel/`, sets `PYTHONPATH` to that extraction root, and executes the configured smoke script under `mayapy`.

### `assemble`

Finds the newest matching wheel in `dist/<target>/`, extracts package files into `dist/module/<target>/<ModuleName>/contents/scripts/`, skips wheel metadata directories, and writes `<ModuleName>.mod`.

### `run`

Runs the full pipeline in order:

1. `create-env` when `--ensure-env` is set and the env is missing
2. `build`
3. `smoke` unless `--skip-smoke`
4. `assemble` unless `--skip-assemble`

## Output contract

Success:

- human mode writes readable lines to stdout
- JSON mode writes one formatted JSON object to stdout

Errors:

- errors are plain text on stderr
- errors are not JSON, even when `--json` is set
- verbose subprocess tracing is written to stderr

Dry-run behavior:

- `--dry-run` previews deletions and subprocesses
- it does not change files
- `run --dry-run` returns one dry-run payload per included step
- target-aware dry-run payloads include the resolved `target`
- `create-env --dry-run` also reports the resolved `python_version` and generated environment file path

Doctor behavior:

- reports the resolved config and explicit `mayapy` runtime metadata
- includes probe success and target-platform match checks
- keeps probe failures in the doctor payload instead of prompting or reading stdin

## Safety contract

These commands share the same cleanup rules:

- `create-env`
- `build`
- `smoke`
- `assemble`
- `run`

Rules:

- destructive cleanup is blocked unless `--force` is provided
- `--dry-run` shows the deletion plan first
- the CLI does not prompt
- the CLI does not read stdin

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | success |
| `2` | usage error, validation error, or destructive action blocked until `--force` |
| `3` | dependency or setup failure |
| `4` | build failure |
| `5` | smoke failure |
| `6` | assemble failure |
| `130` | interrupted by Ctrl-C |

## Examples

```powershell
maya-cython-compile --version
maya-cython-compile config show --json
maya-cython-compile --target windows-2025 doctor
maya-cython-compile --target windows-2025 create-env --dry-run
maya-cython-compile --target windows-2025 build --force --verbose
maya-cython-compile --target windows-2025 smoke --force
maya-cython-compile --target windows-2025 assemble --force --module-name StudioTool --maya-version 2025
maya-cython-compile --target windows-2025 run --ensure-env --force
```
