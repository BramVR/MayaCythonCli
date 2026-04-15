# Pipeline Quickstart

Date: 2026-04-15

This is the practical guide for the current repo state.

Project name: `MayaCythonCli`

## Goal

Build a Maya-targeted Cython package from a normal Conda environment, then validate it under Maya's own Python runtime.

Current default scaffold target:

- Maya 2025
- Windows
- CPython ABI `cp311`

## How the pipeline works

Build side:

- Conda env supplies `python`, `Cython`, `setuptools`, and `wheel`.
- `setup.py` compiles Python modules into extension modules.
- Maya headers and `python311.lib` are injected through environment variables.

Runtime side:

- `mayapy` is used only for validation.
- the built wheel is unpacked and imported under Maya's Python runtime.
- a Maya module layout is assembled from the wheel.

## Local assumptions

Current defaults in the scripts assume:

- Conda is at `C:\Users\ZO\anaconda3\condabin\conda.bat`
- Maya 2025 is at `C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe`

If those differ on another machine, update the script parameters or defaults first.

## One-time setup

Create the build env:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\create-conda-env.ps1
```

This creates:

- `.conda/maya-cython-build`

The environment is defined in:

- [environment.yml](../environment.yml)

## Build

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-package.ps1
```

What it does:

- resolves the Maya root from `mayapy.exe`,
- finds the actual Maya Python headers,
- finds the Maya Python import library automatically,
- runs the build inside the Conda env,
- writes the wheel to `dist/`.

Expected output:

- a wheel for the distribution configured in [build-config.json](../build-config.json)

## Smoke test

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke-package.ps1
```

What it checks:

- the configured package imports under `mayapy`,
- the compiled module imports,
- packaged JSON resources are available at runtime,
- the scaffold entrypoint works.

Current smoke staging path:

- `build/smoke/wheel/`

## Assemble Maya module

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\assemble-module.ps1
```

Expected output:

- `dist/module/<ModuleName>/<ModuleName>.mod`
- `dist/module/<ModuleName>/contents/scripts/<package>/`

This is the current Maya-facing package layout.

## Current scaffold package shape

Compiled modules:

- `gg_maya_tool._cy_logic`

Python support files kept uncompiled:

- `gg_maya_tool.__init__`
- `gg_maya_tool.bootstrap`
- `gg_maya_tool._resources`

Bundled data files:

- `tool_manifest.json`

## Why this split exists

The scaffold is intentionally small so the repo can be committed cleanly without carrying a local test import.

For a real production tool, the better structure is:

- Python bootstrap and UI entrypoints stay Python,
- internal logic modules are compiled,
- data files are package-relative,
- deployment happens through Maya modules, not source-path hacks.

## Known issues

- Maya 2025 emits a PySide/shiboken NumPy warning during UI-related imports.
- `setup.py bdist_wheel` is used right now because `python -m build` hit sandbox/tempdir issues in this session.
- Local research/build output directories are intentionally ignored by Git.

## Recommended next step

Replace `src/gg_maya_tool` with the first real tracked tool package and update [build-config.json](../build-config.json) to match.
