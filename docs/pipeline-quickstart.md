# Pipeline Quickstart

Date: 2026-04-15

## Goal

Build a Maya-targeted Cython wheel from a normal Python environment, validate it under `mayapy`, and assemble a Maya module layout from the produced wheel.

The current scaffold is configured for:

- Windows
- Autodesk Maya 2025
- CPython ABI `cp311`

## Prereqs

You need:

- Autodesk Maya installed locally
- Conda available locally
- Visual Studio C++ build tools available

The default local paths are:

- Conda: `%USERPROFILE%\anaconda3\condabin\conda.bat`
- `mayapy`: `C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe`
- build env: `.conda/maya-cython-build`

Override them with CLI flags, environment variables, or `<repo-root>/.maya-cython-compile.json`.

That config file is intentionally repo-scoped. The CLI does not search home-directory, XDG, `%APPDATA%`, or system-level config locations.

## One-Time Setup

Install the CLI in editable mode if you want the `maya-cython-compile` command available directly:

```powershell
pip install -e .
```

If you do not want to install it yet, the compatibility wrappers in [../scripts](../scripts) still work and delegate into the CLI.

## Start With Doctor

Check the resolved paths and Maya runtime discovery first:

```powershell
maya-cython-compile doctor
```

Machine-readable output:

```powershell
maya-cython-compile doctor --json
```

`doctor` reports:

- resolved config values
- whether Conda exists
- whether the configured env path exists
- whether `mayapy` exists
- whether Maya headers and import libraries can be resolved

## Create the Conda Env

```powershell
maya-cython-compile create-env --dry-run
maya-cython-compile create-env --force
```

This creates or refreshes:

- `.conda/maya-cython-build`

From:

- [../environment.yml](../environment.yml)

If the env already exists, the CLI refuses to refresh it unless you pass `--force`.

## Build the Wheel

```powershell
maya-cython-compile build --dry-run
maya-cython-compile build --force
```

What happens:

- the CLI validates the Conda env exists
- the Maya Python include and lib paths are discovered from `mayapy`
- old build artifacts under `build/` and stale `*.egg-info/` may be removed
- a temporary build tree is written under `build/target-build/`
- `setup.py bdist_wheel` runs inside the configured Conda env
- the built wheel is written to `dist/`

Use `--dry-run` first to inspect cleanup targets. Without `--force`, destructive cleanup fails fast and the CLI does not prompt.

## Run the Smoke Check

```powershell
maya-cython-compile smoke --dry-run
maya-cython-compile smoke --force
```

What it validates:

- the configured package imports under `mayapy`
- the configured compiled modules import
- the configured smoke resource exists inside the package
- the configured smoke callable returns successfully

The wheel is unpacked under:

- `build/smoke/wheel/`

If that unpack directory already exists, `smoke` treats it as a destructive replace and uses the same `--dry-run` / `--force` contract.

## Assemble the Maya Module

```powershell
maya-cython-compile assemble --dry-run
maya-cython-compile assemble --force
```

Expected output:

- `dist/module/<ModuleName>/<ModuleName>.mod`
- `dist/module/<ModuleName>/contents/scripts/<package>/`

Assembly skips wheel metadata directories such as `.dist-info` and `.data`.

If `dist/module/<ModuleName>/` already exists, `assemble` requires `--force` before replacing it.

## Non-interactive Notes

- The CLI does not prompt and does not read from stdin.
- `--no-input` is not needed because non-interactive behavior is the default contract.
- Shell completion is not implemented in this repo today.
- On Ctrl-C, expect a non-zero exit. Python-handled interrupts print `Interrupted.` and return `130`; some Windows shells may instead report `0xC000013A`.

## Run the Full Flow

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

## Current Scaffold

Tracked target metadata lives in [../build-config.json](../build-config.json).

Current sample target package:

- [../src/maya_tool](../src/maya_tool)

Compiled modules:

- `maya_tool._cy_logic`

Python modules kept uncompiled:

- `maya_tool.__init__`
- `maya_tool.bootstrap`
- `maya_tool._resources`

Bundled data files:

- `tool_manifest.json`

## Next Step for a Real Tool

Replace [../src/maya_tool](../src/maya_tool) with the real package you want to ship, then update [../build-config.json](../build-config.json) so the CLI compiles and assembles the right target.
