# Pipeline Quickstart

Date: 2026-04-15

Project name: `maya-cython-compile`

## Goal

Build a Maya-targeted Cython package from a normal Conda environment, validate it under Maya's Python runtime, and assemble a Maya module layout from the produced wheel.

Current default scaffold target:

- Maya 2025
- Windows
- CPython ABI `cp311`

## CLI shape

Primary commands:

- `maya-cython-compile doctor`
- `maya-cython-compile create-env`
- `maya-cython-compile build`
- `maya-cython-compile smoke`
- `maya-cython-compile assemble`
- `maya-cython-compile run`

Optional local config file:

- `.maya-cython-compile.json`

Show resolved config:

```powershell
maya-cython-compile config show --json
```

## How the pipeline works

Build side:

- Conda env supplies `python`, `Cython`, `setuptools`, and `wheel`.
- The CLI prepares a temporary target build tree from [build-config.json](../build-config.json).
- Maya headers and the Python import library are discovered from `mayapy.exe` and injected through environment variables.

Runtime side:

- `mayapy` is used only for validation.
- The built wheel is unpacked under `build/smoke/wheel/` and imported from there.
- Module assembly expands the wheel into `dist/module/<ModuleName>/contents/scripts/`.

## Local assumptions

Default path assumptions:

- Conda: `C:\Users\ZO\anaconda3\condabin\conda.bat`
- Maya 2025: `C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe`

Override them with:

- CLI flags
- environment variables
- `.maya-cython-compile.json`

## One-time setup

Install the CLI in editable mode if you want the `maya-cython-compile` command available globally in the repo environment:

```powershell
pip install -e .
```

Or keep using the compatibility wrappers under [scripts](../scripts).

## Doctor

Start here:

```powershell
maya-cython-compile doctor
```

It reports:

- resolved config paths
- whether Conda exists
- whether the build env exists
- whether `mayapy` exists
- whether Maya headers/libs can be discovered

## Create the Conda env

```powershell
maya-cython-compile create-env
```

This creates:

- `.conda/maya-cython-build`

The environment definition is:

- [environment.yml](../environment.yml)

## Build

```powershell
maya-cython-compile build
```

What it does:

- resolves the Maya root from `mayapy.exe`
- finds the Maya Python headers
- finds the Maya Python import library
- creates a temporary build tree from the tracked target package
- runs `bdist_wheel` inside the configured Conda env
- writes the wheel to `dist/`

## Smoke test

```powershell
maya-cython-compile smoke
```

What it checks:

- the configured package imports under `mayapy`
- the configured compiled modules import
- the configured smoke resource exists inside the package
- the configured smoke callable works

## Assemble Maya module

```powershell
maya-cython-compile assemble
```

Expected output:

- `dist/module/<ModuleName>/<ModuleName>.mod`
- `dist/module/<ModuleName>/contents/scripts/<package>/`

Assembly now skips wheel metadata directories when unpacking into the Maya module payload.

## Run the full pipeline

```powershell
maya-cython-compile run --ensure-env
```

Useful flags:

- `--skip-smoke`
- `--skip-assemble`
- `--module-name <name>`
- `--maya-version <version>`

## Current scaffold package shape

Compiled modules:

- `maya_tool._cy_logic`

Python support files kept uncompiled:

- `maya_tool.__init__`
- `maya_tool.bootstrap`
- `maya_tool._resources`

Bundled data files:

- `tool_manifest.json`

## Why this split exists

For a real production tool, the preferred structure is still:

- Python bootstrap and UI entrypoints stay Python
- internal logic modules are compiled
- data files remain package-relative
- deployment happens through Maya modules

The CLI is now separate from the Maya target package so the repo can be installed as a tool without requiring Maya build variables just to install the command itself.

## Recommended next step

Replace [src/maya_tool](../src/maya_tool) with the first real tracked tool package and update [build-config.json](../build-config.json) to match.
