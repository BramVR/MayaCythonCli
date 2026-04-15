# CLI Reference

Date: 2026-04-15

## Command Shape

The console entrypoint is:

```powershell
maya-cython-compile
```

The CLI is implemented in [../src/maya_cython_compile/cli.py](../src/maya_cython_compile/cli.py) and exposes these commands:

- `config show`
- `doctor`
- `create-env`
- `build`
- `smoke`
- `assemble`
- `run`

## Global Flags

Available on every command:

- `--repo-root <path>`: repo root used for config and outputs
- `--config <path>`: override local config file
- `--json`: emit JSON to stdout
- `--verbose`: print subprocess commands to stderr
- `--conda-exe <path>`: override Conda executable path
- `--env-path <path>`: override local Conda env path
- `--maya-py <path>`: override `mayapy` path

The CLI normalizes global flags so they can appear before or after the subcommand:

```powershell
maya-cython-compile --json doctor
maya-cython-compile doctor --json
```

## Commands

### `config show`

Show the fully resolved configuration:

```powershell
maya-cython-compile config show
maya-cython-compile config show --json
```

Returned fields include:

- repo root
- local config path
- Conda path
- env path
- `mayapy` path
- distribution and package metadata from `build-config.json`
- smoke configuration

### `doctor`

Inspect the local machine assumptions without building:

```powershell
maya-cython-compile doctor
```

Checks returned:

- `conda_exe_exists`
- `env_exists`
- `maya_py_exists`
- `maya_include_exists`
- `maya_lib_exists`

The payload also includes discovered Maya runtime values:

- `maya_py`
- `include_dir`
- `lib_dir`
- `lib_name`

### `create-env`

Create or refresh the configured build env:

```powershell
maya-cython-compile create-env
```

Implementation details:

- runs `conda env create --prefix <env> --force --file environment.yml`
- uses the resolved `conda_exe`
- fails fast if Conda is missing

### `build`

Build the configured wheel:

```powershell
maya-cython-compile build
```

Implementation details:

- requires the configured env path to exist
- discovers Maya include and lib locations from `mayapy`
- writes a temporary target build tree under `build/target-build/`
- runs `python setup.py bdist_wheel --dist-dir dist` inside the Conda env
- returns the newest wheel under `dist/`

### `smoke`

Run the smoke validation under `mayapy`:

```powershell
maya-cython-compile smoke
```

Implementation details:

- unpacks the newest wheel into `build/smoke/wheel/`
- sets `PYTHONPATH` to the unpacked wheel
- executes the generated smoke script with `mayapy -c`
- returns captured smoke output

### `assemble`

Create a Maya module payload from the newest wheel:

```powershell
maya-cython-compile assemble
maya-cython-compile assemble --module-name StudioTool --maya-version 2025
```

Implementation details:

- unpacks the wheel into `dist/module/<ModuleName>/contents/scripts/`
- skips `.dist-info` and `.data` directories
- writes `<ModuleName>.mod` beside `contents/`

### `run`

Run the full pipeline:

```powershell
maya-cython-compile run --ensure-env
```

Optional flags:

- `--ensure-env`: create the env first if it is missing
- `--skip-smoke`: skip `mayapy` validation
- `--skip-assemble`: skip module assembly
- `--module-name <name>`: override module name for assembly
- `--maya-version <version>`: override Maya version for assembly

Order of operations:

- create env if requested and missing
- build
- smoke unless skipped
- assemble unless skipped

## Output Contract

Human mode prints simple text lines to stdout.

JSON mode prints a structured payload to stdout:

```powershell
maya-cython-compile doctor --json
maya-cython-compile config show --json
```

Errors are printed to stderr and the process exits non-zero.

## Config Resolution

Resolution precedence is:

1. CLI flags
2. environment variables
3. `.maya-cython-compile.json`
4. built-in defaults

Supported environment variables:

- `MAYA_CYTHON_COMPILE_CONDA_EXE`
- `MAYA_CYTHON_COMPILE_ENV_PATH`
- `MAYA_CYTHON_COMPILE_MAYA_PY`

## Compatibility Wrappers

These scripts still exist and delegate into the CLI:

- [../scripts/create-conda-env.ps1](../scripts/create-conda-env.ps1)
- [../scripts/build-package.ps1](../scripts/build-package.ps1)
- [../scripts/smoke-package.ps1](../scripts/smoke-package.ps1)
- [../scripts/assemble-module.ps1](../scripts/assemble-module.ps1)
