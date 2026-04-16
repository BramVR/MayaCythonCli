---
summary: "CLI commands, global flags, output modes, and failure codes."
read_when:
  - "When changing command-line behavior or adding flags."
  - "When updating JSON or text output contracts."
---

# CLI

`maya-cython-compile` is a non-interactive Windows-first CLI for building a Maya-compatible Cython wheel, validating it under `mayapy`, and assembling a Maya module payload.

## Usage

```text
maya-cython-compile
  [--repo-root PATH]
  [--config PATH]
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
| `--json` | emit JSON to stdout |
| `--verbose` | print spawned subprocess commands to stderr |
| `--conda-exe PATH` | override Conda executable |
| `--env-path PATH` | override build env location |
| `--maya-py PATH` | override `mayapy` path |
| `--version` | print version and exit |

Flags that are not implemented:

- `--plain`
- `--quiet`

## Commands

### `config show`

Prints the fully resolved config from repo metadata, local config, env vars, and CLI overrides.

### `doctor`

Checks whether the configured Conda executable, env path, and `mayapy` path exist, then probes Maya include and import-lib paths from `mayapy`.

### `create-env`

Creates the local Conda build environment from [../environment.yml](../environment.yml). If the target env already exists, the command treats that as a replace operation and requires `--force`.

### `build`

Builds the configured wheel inside the resolved Conda env. It validates Maya runtime discovery, cleans prior build outputs when allowed, prepares `build/target-build/`, and writes the newest wheel to `dist/`.

### `smoke`

Finds the newest matching wheel in `dist/`, extracts it to `build/smoke/wheel/`, sets `PYTHONPATH` to that extraction root, and executes the configured smoke script under `mayapy`.

### `assemble`

Finds the newest matching wheel in `dist/`, extracts package files into `dist/module/<ModuleName>/contents/scripts/`, skips wheel metadata directories, and writes `<ModuleName>.mod`.

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
maya-cython-compile config show
maya-cython-compile doctor --json
maya-cython-compile create-env --dry-run
maya-cython-compile build --force --verbose
maya-cython-compile smoke --force
maya-cython-compile assemble --force --module-name StudioTool --maya-version 2025
maya-cython-compile run --ensure-env --force
```
