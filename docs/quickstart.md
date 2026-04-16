---
summary: "First-run setup and the normal create-env, build, smoke, and assemble flow."
read_when:
  - "When setting up the repo on a new Windows machine."
  - "When you need the shortest safe path through the pipeline."
---

# Quickstart

Build a Maya-targeted Cython wheel from a normal Python environment, validate it under `mayapy`, then assemble a Maya module layout from the built wheel.

## Current scaffold

- platform: Windows
- Maya version: `2025`
- target package: `src/maya_tool`
- compiled module: `maya_tool._cy_logic`
- bundled data: `tool_manifest.json`

Tracked target metadata lives in [../build-config.json](../build-config.json).

## Prereqs

You need:

- Autodesk Maya installed locally
- Conda available locally
- Visual Studio C++ build tools

Default paths:

- Conda: `%USERPROFILE%\anaconda3\condabin\conda.bat`
- `mayapy`: `C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe`
- build env: `.conda/maya-cython-build`

Override them with CLI flags, environment variables, or `<repo-root>/.maya-cython-compile.json`.

## Install the CLI

```powershell
pip install -e .
```

The PowerShell wrappers in [wrappers.md](wrappers.md) can still be used if you do not want to install the CLI globally.

## Start with doctor

```powershell
maya-cython-compile doctor
maya-cython-compile doctor --json
```

`doctor` reports:

- resolved config values
- whether Conda exists
- whether the configured env path exists
- whether `mayapy` exists
- whether Maya headers and import libraries can be resolved

## Create the build env

```powershell
maya-cython-compile create-env --dry-run
maya-cython-compile create-env --force
```

This creates or refreshes the Conda env from [../environment.yml](../environment.yml). If the target env already exists, the command refuses to replace it unless you pass `--force`.

## Build the wheel

```powershell
maya-cython-compile build --dry-run
maya-cython-compile build --force
```

The build step:

- validates the env exists
- resolves Maya include and lib paths from `mayapy`
- cleans prior build artifacts when `--force` allows it
- prepares `build/target-build/`
- runs `setup.py bdist_wheel` inside the configured Conda env
- writes the wheel to `dist/`

## Smoke the wheel under Maya

```powershell
maya-cython-compile smoke --dry-run
maya-cython-compile smoke --force
```

The smoke step extracts the newest wheel to `build/smoke/wheel/`, sets `PYTHONPATH` to that extraction root, and validates the configured imports, callable, and resource check under `mayapy`.

## Assemble the Maya module

```powershell
maya-cython-compile assemble --dry-run
maya-cython-compile assemble --force
```

Expected outputs:

- `dist/module/<ModuleName>/<ModuleName>.mod`
- `dist/module/<ModuleName>/contents/scripts/<package>/`

## Run the full flow

```powershell
maya-cython-compile run --dry-run
maya-cython-compile run --ensure-env --force
```

Useful variants:

```powershell
maya-cython-compile run --skip-smoke
maya-cython-compile run --skip-assemble
maya-cython-compile run --force --module-name StudioTool --maya-version 2025
```

## Non-interactive contract

- the CLI does not prompt
- the CLI does not read from stdin
- destructive cleanup is blocked unless `--force` is provided
- `--dry-run` previews deletions and subprocesses without changing files
- Ctrl-C is normalized to `Interrupted.` with exit code `130`

## For a real tool

Replace [../src/maya_tool](../src/maya_tool) with the package you want to ship, then update [../build-config.json](../build-config.json) so the pipeline compiles and assembles the correct target.
