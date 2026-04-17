---
summary: "First-run setup and the normal create-env, build, smoke, and assemble flow."
read_when:
  - "When setting up the repo on a new Windows machine."
  - "When you need the shortest safe path through the pipeline."
---

# Quickstart

Build a Maya-targeted Cython wheel from a normal Python environment, validate it under `mayapy`, then assemble a Maya module layout from the built wheel.

## Current scaffold

- default target: `windows-2025`
- platform: Windows
- Maya version: `2025`
- target Python: `3.11`
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

- Conda: `conda` from `PATH`, otherwise `%USERPROFILE%\anaconda3\condabin\conda.bat` on Windows
- `mayapy`: `C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe`
- build env: `.conda/<target>`

Override them with CLI flags, environment variables, or `<repo-root>/.maya-cython-compile.json`.

If you build multiple targets from one repo clone, keep the default target-specific env paths or set explicit target-specific `env_path`, `maya_py`, and `conda_exe` entries in `.maya-cython-compile.json.targets`.

## Install the CLI

```powershell
pip install -e .
```

The PowerShell wrappers in [wrappers.md](wrappers.md) can still be used if you do not want to install the CLI globally.

## Start with doctor

```powershell
maya-cython-compile --target windows-2025 doctor
maya-cython-compile --target windows-2025 doctor --json
```

`doctor` reports:

- the resolved config values for the selected target
- whether Conda exists
- whether the configured env path exists
- whether `mayapy` exists
- whether the `mayapy` probe succeeded
- whether the probed runtime platform matches the selected target
- the resolved Python include path and Python library metadata reported by `mayapy`

## Create the build env

```powershell
maya-cython-compile --target windows-2025 create-env --dry-run
maya-cython-compile --target windows-2025 create-env --force
```

This creates or refreshes the selected target's Conda env from [../environment.yml](../environment.yml). The CLI writes a target-scoped environment file, pins its `python=` dependency from the resolved target `python_version`, and then runs Conda against that file. If that env already exists, the command refuses to replace it unless you pass `--force`.

## Build the wheel

```powershell
maya-cython-compile --target windows-2025 build --dry-run
maya-cython-compile --target windows-2025 build --force
```

The build step:

- validates the env exists
- probes `mayapy` directly for Python include and library metadata
- rejects a selected target when its platform or Python version does not match the probed `mayapy` runtime
- cleans prior target-scoped build artifacts when `--force` allows it
- prepares `build/target-build/<target>/`
- runs `setup.py bdist_wheel` inside the configured Conda env
- writes the wheel to `dist/<target>/`

## Smoke the wheel under Maya

```powershell
maya-cython-compile --target windows-2025 smoke --dry-run
maya-cython-compile --target windows-2025 smoke --force
```

The smoke step extracts the newest wheel from `dist/<target>/` to `build/smoke/<target>/wheel/`, sets `PYTHONPATH` to that extraction root, and validates the configured imports, callable, and resource check under `mayapy`.

## Assemble the Maya module

```powershell
maya-cython-compile --target windows-2025 assemble --dry-run
maya-cython-compile --target windows-2025 assemble --force
```

Expected outputs:

- `dist/module/<target>/<ModuleName>/<ModuleName>.mod`
- `dist/module/<target>/<ModuleName>/contents/scripts/<package>/`

## Run the full flow

```powershell
maya-cython-compile --target windows-2025 run --dry-run
maya-cython-compile --target windows-2025 run --ensure-env --force
```

Useful variants:

```powershell
maya-cython-compile --target windows-2025 run --skip-smoke
maya-cython-compile --target windows-2025 run --skip-assemble
maya-cython-compile --target windows-2025 run --force --module-name StudioTool --maya-version 2025
```

Sharing one Conda env across multiple targets is only safe when those targets use the same Python ABI and compatible build dependencies. The default `.conda/<target>` layout avoids cross-target wheel and interpreter drift.

## Non-interactive contract

- the CLI does not prompt
- the CLI does not read from stdin
- destructive cleanup is blocked unless `--force` is provided
- `--dry-run` previews deletions and subprocesses without changing files
- Ctrl-C is normalized to `Interrupted.` with exit code `130`

## For a real tool

Replace [../src/maya_tool](../src/maya_tool) with the package you want to ship, then update [../build-config.json](../build-config.json) so the pipeline compiles and assembles the correct target or set of targets.
