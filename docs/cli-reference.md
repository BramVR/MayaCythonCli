# CLI Specification

Date: 2026-04-16

This document is the implementation contract for `maya-cython-compile`. It describes externally observable CLI behavior, argument handling, output shape, side effects, and failure modes.

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

Global flags are accepted before or after the subcommand. Examples:

```powershell
maya-cython-compile --json doctor
maya-cython-compile doctor --json
maya-cython-compile run --verbose --force
```

## Configuration Contract

The CLI resolves configuration in this precedence order:

1. CLI flags
2. Environment variables
3. Local config file
4. Built-in defaults

### Repo-scoped config only

The local config layer is intentionally repo-scoped.

By default, the CLI reads exactly `<repo-root>/.maya-cython-compile.json`. If `--config PATH` is provided, the CLI reads that exact file instead.

There is currently no user-level or system-level config discovery. The CLI does not search XDG locations, home-directory dotfiles, `%APPDATA%`, or system config paths.

### Required repo input

`<repo-root>/build-config.json` must exist and contain:

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `distribution_name` | string | yes | none |
| `package_name` | string | yes | none |
| `package_dir` | string | yes | none |
| `version` | string | yes | none |
| `compiled_modules` | array of strings | yes | none |
| `module_name` | string | no | `package_name` |
| `maya_version` | string or number | no | `"2025"` |
| `package_data` | array of strings | no | `[]` |
| `smoke.callable` | string or null | no | `null` |
| `smoke.compiled_modules` | array of strings | no | `compiled_modules` |
| `smoke.resource_check` | string or null | no | `null` |

### Local config file

Default local config path: `<repo-root>/.maya-cython-compile.json`

Unless `--config` is provided, this is the only config file location the CLI will read.

Supported keys:

| Key | Type | Meaning |
| --- | --- | --- |
| `conda_exe` | path string | Conda entrypoint |
| `env_path` | path string | Local build env path |
| `maya_py` | path string | `mayapy` executable |

### Environment variables

| Variable | Meaning |
| --- | --- |
| `MAYA_CYTHON_COMPILE_CONDA_EXE` | Overrides `conda_exe` |
| `MAYA_CYTHON_COMPILE_ENV_PATH` | Overrides `env_path` |
| `MAYA_CYTHON_COMPILE_MAYA_PY` | Overrides `maya_py` |

### Built-in defaults

| Setting | Default |
| --- | --- |
| `conda_exe` | `%USERPROFILE%\anaconda3\condabin\conda.bat` |
| `env_path` | `.conda/maya-cython-build` |
| `maya_py` | `C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe` |

Relative paths from CLI flags, env vars, or `.maya-cython-compile.json` resolve relative to `repo_root`.

## Global Flags

| Flag | Type | Default | Scope | Effect | Example |
| --- | --- | --- | --- | --- | --- |
| `--repo-root` | path | `.` | all commands | Base directory for config lookup, build inputs, and outputs | `--repo-root C:\repo` |
| `--config` | path | `<repo-root>\.maya-cython-compile.json` | all commands | Uses an alternate local config file | `--config C:\repo\alt-config.json` |
| `--json` | boolean | `false` | all commands | Emits JSON payloads to stdout instead of human text | `doctor --json` |
| `--verbose` | boolean | `false` | all commands | Prints each spawned subprocess command to stderr before execution; only affects commands that spawn subprocesses | `build --verbose` |
| `--conda-exe` | path | resolved from precedence chain | all commands | Overrides Conda executable | `--conda-exe C:\Miniconda\condabin\conda.bat` |
| `--env-path` | path | resolved from precedence chain | all commands | Overrides build env location | `--env-path .conda\custom-env` |
| `--maya-py` | path | resolved from precedence chain | all commands | Overrides `mayapy` location; used by commands that probe or execute Maya Python | `--maya-py C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe` |
| `--version` | boolean | `false` | process-wide | Prints `maya-cython-compile <version>` and exits `0` without running a command | `maya-cython-compile --version` |

Flags that are not implemented:

- `--plain`
- `--quiet`

## I/O Contract

- Success, human mode: write human-readable lines to stdout.
- Success, JSON mode: write a single JSON object to stdout, formatted with indentation.
- Errors: write plain text to stderr. Errors are never JSON, even when `--json` is set.
- Verbose subprocess tracing: write `$ <command...>` lines to stderr.
- `KeyboardInterrupt` is normalized: print `Interrupted.` to stderr and exit `130`.
- Only `CliError`, `ValueError`, and `KeyboardInterrupt` are normalized into the documented stderr-plus-exit-code contract. Other uncaught exceptions use the interpreter's default traceback behavior.

## Non-interactive Behavior

- The CLI does not prompt.
- The CLI does not read from stdin.
- There is no `--no-input` flag because the CLI is already non-interactive by contract.
- Commands that would delete existing outputs fail with exit code `2` unless you opt in with `--force`.

## Shell Completion

- Shell completion is currently unsupported and out of scope for this CLI.
- There is no built-in completion generator or completion script in this repo today.

## Signal / Ctrl-C Behavior

- Interrupting the CLI stops the current operation and exits non-zero.
- Direct `KeyboardInterrupt` handling prints `Interrupted.` to stderr and exits `130`.
- Interrupted subprocesses are also normalized to `Interrupted.` with exit `130`, including Windows `STATUS_CONTROL_C_EXIT` (`0xC000013A`) return codes.

Human output rules:

- `config show`: first line is `Config`, then one `key: value` line per resolved field.
- `doctor`: first line is `Doctor`, then one `key: ok|missing` line per check, then Maya runtime lines.
- Non-dry-run commands other than `config show` and `doctor`: one `key: value` line per top-level result field.
- Dry-run commands: first line is `Dry run`.
- Dry-run `run`: each step is rendered under `[create_env]`, `[build]`, `[smoke]`, and `[assemble]` headers when included.

## Destructive Output Safety

The following commands share one deletion/force contract:

- `create-env`
- `build`
- `smoke`
- `assemble`
- `run`

Shared rules:

- `--dry-run`: report planned deletions and subprocesses; do not modify files.
- `--force`: allow deletion without prompting.
- Without `--force`: fail with exit code `2` before deleting anything.

`run` performs the deletion check once for the combined pipeline cleanup plan, then executes inner steps with forced deletion enabled.

## Command Contracts

### `config show`

**Subcommand flags**

None.

**Inputs**

- Resolved config sources from `repo_root`, optional local config file, environment variables, and CLI overrides.
- `build-config.json` is required.

**Outputs**

Human mode:

```text
Config
repo_root: ...
local_config_path: ...
conda_exe: ...
env_path: ...
maya_py: ...
distribution_name: ...
package_name: ...
package_dir: ...
module_name: ...
maya_version: ...
version: ...
compiled_modules: [...]
package_data: [...]
smoke: {...}
```

JSON mode:

```json
{
  "config": {
    "repo_root": "...",
    "local_config_path": "...",
    "conda_exe": "...",
    "env_path": "...",
    "maya_py": "...",
    "distribution_name": "...",
    "package_name": "...",
    "package_dir": "...",
    "module_name": "...",
    "maya_version": "...",
    "version": "...",
    "compiled_modules": ["..."],
    "package_data": ["..."],
    "smoke": {
      "callable": "...",
      "compiled_modules": ["..."],
      "resource_check": "..."
    }
  }
}
```

**Side effects**

None.

**Failure modes**

- Exit `2` if arguments are invalid or `build-config.json` cannot be parsed as expected.

### `doctor`

**Subcommand flags**

None.

**Inputs**

- Same config resolution as `config show`.
- Resolved `mayapy` path.

**Behavior**

- Checks whether `conda_exe`, `env_path`, and `maya_py` exist.
- Discovers Maya runtime paths from `mayapy`:
  - Maya root is `mayapy.parent.parent`
  - include dir is `<maya_root>/Python/Include`, else the first recursive `Python.h` match under the Maya root
  - lib dir is `<maya_root>/lib`
  - lib name is the stem of the first `python*.lib` file in that lib dir

**Outputs**

JSON mode returns:

```json
{
  "config": { "...": "..." },
  "checks": {
    "conda_exe_exists": true,
    "env_exists": true,
    "maya_py_exists": true,
    "maya_include_exists": true,
    "maya_lib_exists": true
  },
  "maya_runtime": {
    "maya_py": "...",
    "include_dir": "...",
    "lib_dir": "...",
    "lib_name": "python311"
  }
}
```

Human mode prints only the `checks` and `maya_runtime` fields, not the nested `config` object.

**Side effects**

None.

**Failure modes**

- Exit `2` if arguments are invalid or config loading fails.
- Missing files do not fail the command; they are reported in `checks`.

### `create-env`

**Subcommand flags**

| Flag | Type | Default | Meaning |
| --- | --- | --- | --- |
| `--dry-run` | boolean | `false` | Preview deletions and subprocess command |
| `--force` | boolean | `false` | Allow replacing an existing env |

**Inputs**

- Resolved `conda_exe`
- Resolved `env_path`
- `<repo-root>/environment.yml`

**Behavior**

- If `env_path` does not exist, create the env.
- If `env_path` exists, treat it as a replace operation.
- Spawn:

```text
cmd.exe /c <conda_exe> env create --prefix <env_path> [--force] --file <repo-root>\environment.yml
```

The subprocess includes `--force` when the target env path already exists.

**Outputs**

Success JSON:

```json
{
  "env_path": "..."
}
```

Dry-run JSON:

```json
{
  "dry_run": true,
  "command": "create-env",
  "delete": [
    {
      "path": "...",
      "reason": "replace existing Conda environment"
    }
  ],
  "would_run": ["cmd.exe", "/c", "..."],
  "env_path": "..."
}
```

**Side effects**

- May delete the existing env directory at `env_path`.
- Creates a Conda env at `env_path`.

**Failure modes**

- Exit `2` if deletion would occur without `--force`.
- Exit `130` if the command is interrupted with Ctrl-C.
- Exit `3` if `conda_exe` does not exist or the Conda subprocess fails.

### `build`

**Subcommand flags**

| Flag | Type | Default | Meaning |
| --- | --- | --- | --- |
| `--dry-run` | boolean | `false` | Preview cleanup and build subprocess |
| `--force` | boolean | `false` | Allow deleting prior build artifacts |

**Inputs**

- Existing Conda env at `env_path`
- Resolved `mayapy`
- `build-config.json`
- Python package sources under `package_dir`

**Behavior**

- Requires `env_path` to exist.
- Resolves Maya include/lib information from `mayapy`.
- Plans deletion of:
  - `<repo-root>/build/lib.*`
  - `<repo-root>/build/bdist.*`
  - `<repo-root>/build/temp.*`
  - `<repo-root>/build/cython`
  - `<repo-root>/build/target-build`
  - `<repo-root>/build/tmp`
  - `<repo-root>/*.egg-info` directories
- Rebuilds a temporary source tree under `<repo-root>/build/target-build`.
- Creates `<repo-root>/build/tmp` and sets:
  - `MAYA_PYTHON_INCLUDE`
  - `MAYA_PYTHON_LIBDIR`
  - `MAYA_PYTHON_LIBNAME`
  - `TEMP`
  - `TMP`
- Spawns from `<repo-root>/build/target-build`:

```text
cmd.exe /c <conda_exe> run --prefix <env_path> python setup.py bdist_wheel --dist-dir <repo-root>\dist
```

- Returns the newest wheel in `<repo-root>/dist` whose filename matches `distribution_name` with `-` normalized to `_`.

**Outputs**

Success JSON:

```json
{
  "wheel": "..."
}
```

Dry-run JSON:

```json
{
  "dry_run": true,
  "command": "build",
  "delete": [
    {
      "path": "...",
      "reason": "..."
    }
  ],
  "would_run": ["cmd.exe", "/c", "..."],
  "dist_dir": "..."
}
```

**Side effects**

- Deletes previous build artifacts.
- Creates `build/target-build`, `build/tmp`, and `dist/`.
- Writes a new wheel file into `dist/`.

**Failure modes**

- Exit `2` if deletion would occur without `--force`.
- Exit `130` if the command is interrupted with Ctrl-C.
- Exit `3` if the env is missing or Maya runtime resolution from `mayapy` fails.
- Exit `4` if the wheel build subprocess fails.

### `smoke`

**Subcommand flags**

| Flag | Type | Default | Meaning |
| --- | --- | --- | --- |
| `--dry-run` | boolean | `false` | Preview extraction cleanup and smoke subprocess |
| `--force` | boolean | `false` | Allow replacing previous smoke extraction |

**Inputs**

- Existing `mayapy`
- Newest built wheel in `<repo-root>/dist`
- Smoke config from `build-config.json`

**Behavior**

- Selects the newest wheel matching `distribution_name` with `-` normalized to `_`.
- Extracts that wheel to `<repo-root>/build/smoke/wheel`.
- Sets `PYTHONPATH=<repo-root>/build/smoke/wheel`.
- Executes:

```text
<maya_py> -c "<generated smoke script>"
```

Generated smoke script behavior:

- imports `package_name`
- imports each module listed in `smoke.compiled_modules`
- if `smoke.callable` is set, prints `getattr(package, smoke.callable)()`
- if `smoke.resource_check` is set, prints whether that resource exists in the package

**Outputs**

Success JSON:

```json
{
  "wheel": "...",
  "smoke_output": ["line 1", "line 2"]
}
```

Dry-run JSON:

```json
{
  "dry_run": true,
  "command": "smoke",
  "delete": [
    {
      "path": "...",
      "reason": "replace previous smoke extraction"
    }
  ],
  "would_run": ["<maya_py>", "-c", "..."],
  "extract_dir": "...",
  "wheel": "..."
}
```

When `smoke` is previewed as part of `run --dry-run`, `wheel` may be `"after build step"` even if no wheel exists yet.

**Side effects**

- May delete `<repo-root>/build/smoke/wheel`.
- Extracts the wheel into `<repo-root>/build/smoke/wheel`.

**Failure modes**

- Exit `2` if deletion would occur without `--force`.
- Exit `3` if `mayapy` does not exist.
- Exit `130` if the command is interrupted with Ctrl-C.
- Exit `5` if no matching wheel exists or the smoke subprocess fails.

### `assemble`

**Subcommand flags**

| Flag | Type | Default | Meaning |
| --- | --- | --- | --- |
| `--dry-run` | boolean | `false` | Preview module output replacement |
| `--force` | boolean | `false` | Allow replacing previous module output |
| `--module-name` | string | `build-config.json: module_name` | Override assembled module directory and `.mod` filename |
| `--maya-version` | string | `build-config.json: maya_version` | Override `.mod` file `MAYAVERSION` token |

**Inputs**

- Newest built wheel in `<repo-root>/dist`
- `module_name`
- `maya_version`

**Behavior**

- Selects the newest wheel matching `distribution_name` with `-` normalized to `_`.
- Uses module root `<repo-root>/dist/module/<module_name>`.
- Extracts wheel contents into `<module_root>/contents/scripts`.
- Skips any top-level wheel entries whose first path segment ends with `.dist-info` or `.data`.
- Writes `<module_root>/<module_name>.mod` with exact content:

```text
+ MAYAVERSION:<maya_version> PLATFORM:win64 <module_name> <build-config.version> .\contents
```

**Outputs**

Success JSON:

```json
{
  "module_root": "...",
  "module_file": "..."
}
```

Dry-run JSON:

```json
{
  "dry_run": true,
  "command": "assemble",
  "delete": [
    {
      "path": "...",
      "reason": "replace previous assembled module output"
    }
  ],
  "module_root": "...",
  "module_file": "...",
  "wheel": "..."
}
```

When `assemble` is previewed as part of `run --dry-run`, `wheel` may be `"after build step"` even if no wheel exists yet.

**Side effects**

- May delete `<repo-root>/dist/module/<module_name>`.
- Creates a Maya module layout under `<repo-root>/dist/module/<module_name>`.

**Failure modes**

- Exit `2` if deletion would occur without `--force`.
- Exit `130` if the command is interrupted with Ctrl-C.
- Exit `6` if no matching wheel exists or module assembly fails.

### `run`

**Subcommand flags**

| Flag | Type | Default | Meaning |
| --- | --- | --- | --- |
| `--dry-run` | boolean | `false` | Preview the full pipeline |
| `--force` | boolean | `false` | Allow the pipeline plan to delete existing outputs |
| `--ensure-env` | boolean | `false` | Run `create-env` first, but only if `env_path` is missing |
| `--skip-smoke` | boolean | `false` | Omit the smoke step |
| `--skip-assemble` | boolean | `false` | Omit the assemble step |
| `--module-name` | string | `build-config.json: module_name` | Override module name for the assemble step |
| `--maya-version` | string | `build-config.json: maya_version` | Override Maya version for the assemble step |

**Inputs**

- Same inputs as the steps it executes.

**Behavior**

- Dry-run order:
  - include `create_env` only when `--ensure-env` is set and `env_path` does not exist
  - always include `build`
  - include `smoke` unless `--skip-smoke`
  - include `assemble` unless `--skip-assemble`
- Non-dry-run order:
  1. require `--force` if combined deletions would occur
  2. run `create-env` only when `--ensure-env` is set and `env_path` does not exist
  3. run `build`
  4. run `smoke` unless skipped
  5. run `assemble` unless skipped
- Inner step executions run with forced deletion enabled because the pipeline-level deletion check already happened.

**Outputs**

Success JSON:

```json
{
  "build": {
    "wheel": "..."
  },
  "smoke": {
    "wheel": "...",
    "smoke_output": ["..."]
  },
  "assemble": {
    "module_root": "...",
    "module_file": "..."
  }
}
```

If `create-env` runs, it is returned as `"create_env": {"env_path": "..."}`. Skipped steps are omitted from the payload.

Dry-run JSON:

```json
{
  "dry_run": true,
  "steps": {
    "build": {
      "dry_run": true,
      "command": "build",
      "delete": [],
      "would_run": ["cmd.exe", "/c", "..."],
      "dist_dir": "..."
    },
    "smoke": {
      "dry_run": true,
      "command": "smoke",
      "delete": [],
      "would_run": ["<maya_py>", "-c", "..."],
      "extract_dir": "...",
      "wheel": "after build step"
    },
    "assemble": {
      "dry_run": true,
      "command": "assemble",
      "delete": [],
      "module_root": "...",
      "module_file": "...",
      "wheel": "after build step"
    }
  }
}
```

**Side effects**

- Union of the executed step side effects.

**Failure modes**

- Exit `2` if the pipeline would delete outputs without `--force`.
- Exit `130` if the pipeline is interrupted with Ctrl-C.
- Exit `3`, `4`, `5`, or `6` from the first failing step.

## Exit Codes

| Code | Meaning |
| --- | --- |
| `0` | success |
| `2` | usage error, invalid arguments, config/validation error, or destructive action blocked until `--force` is provided |
| `3` | dependency/setup failure |
| `4` | build failure |
| `5` | smoke failure |
| `6` | assemble failure |
| `130` | interrupted by Ctrl-C / `KeyboardInterrupt` |

## Examples

```powershell
maya-cython-compile --version
```

```powershell
maya-cython-compile config show
```

```powershell
maya-cython-compile doctor --json
```

```powershell
maya-cython-compile create-env --dry-run --conda-exe "%USERPROFILE%\anaconda3\condabin\conda.bat"
```

```powershell
maya-cython-compile build --force --verbose
```

```powershell
maya-cython-compile smoke --maya-py "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe" --json
```

```powershell
maya-cython-compile assemble --force --module-name StudioTool --maya-version 2025
```

```powershell
maya-cython-compile run --ensure-env --force
```

```powershell
maya-cython-compile run --dry-run --skip-smoke --module-name StudioTool
```

```powershell
maya-cython-compile --repo-root C:\repo --config C:\repo\custom.json doctor
```

## Compatibility Wrappers

These scripts are compatibility entrypoints that delegate into the CLI:

- [../scripts/create-conda-env.ps1](../scripts/create-conda-env.ps1)
- [../scripts/build-package.ps1](../scripts/build-package.ps1)
- [../scripts/smoke-package.ps1](../scripts/smoke-package.ps1)
- [../scripts/assemble-module.ps1](../scripts/assemble-module.ps1)

Wrapper notes:

- Each wrapper exposes the matching safety switches as PowerShell flags: `-DryRun` and `-Force`.
- The wrappers prefer the repo-local interpreter at `.conda\curvenet-build\python.exe` when it exists, then fall back to `py -3`, then `python`.
- That interpreter preference avoids picking an older global Python that cannot run the CLI.
