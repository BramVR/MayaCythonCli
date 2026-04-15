# gg_CythonCompile

Windows-first build pipeline for compiling Maya Python tools with Cython.

Current status:

- research completed,
- Conda-based build flow prototyped,
- generic scaffold created,
- ready for first Git commit without local test imports.

## What this repo does

This repo is for building Python tools into Maya-compatible extension modules without using `mayapy` as the build interpreter.

The current flow is:

1. create a local Conda env for build tools,
2. point the build at an installed Maya runtime,
3. compile selected package modules into `.pyd` binaries,
4. validate imports under `mayapy`,
5. assemble a Maya module package.

This keeps the build toolchain isolated while still targeting Maya's embedded Python ABI.

## Current target

Validated target:

- Windows
- Autodesk Maya 2025
- CPython 3.11 (`cp311`)

The same approach should be extended per Maya/Python target, not assumed portable across all Maya versions.

## Quick start

Prereqs:

- Autodesk Maya installed locally
- Anaconda or Miniconda installed locally
- Visual Studio C++ build tools available

Create the build env:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\create-conda-env.ps1
```

Build the wheel:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-package.ps1
```

Smoke test under Maya:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke-package.ps1
```

Assemble the Maya module layout:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\assemble-module.ps1
```

## Key files

- [environment.yml](C:/PROJECTS/GG/gg_CythonCompile/environment.yml): Conda build environment
- [build-config.json](C:/PROJECTS/GG/gg_CythonCompile/build-config.json): package/build metadata for the scaffold
- [setup.py](C:/PROJECTS/GG/gg_CythonCompile/setup.py): Cython/setuptools build definition
- [scripts/create-conda-env.ps1](C:/PROJECTS/GG/gg_CythonCompile/scripts/create-conda-env.ps1): creates the local Conda env
- [scripts/build-package.ps1](C:/PROJECTS/GG/gg_CythonCompile/scripts/build-package.ps1): compiles the configured package against Maya headers/libs
- [scripts/smoke-package.ps1](C:/PROJECTS/GG/gg_CythonCompile/scripts/smoke-package.ps1): validates the built wheel under `mayapy`
- [scripts/assemble-module.ps1](C:/PROJECTS/GG/gg_CythonCompile/scripts/assemble-module.ps1): creates a `.mod`-based Maya package layout
- [src/gg_maya_tool](C:/PROJECTS/GG/gg_CythonCompile/src/gg_maya_tool): generic package scaffold for the first tracked version

## Outputs

Tracked source stays clean because local build artifacts and local research imports are ignored by Git.

## Known caveats

- The scaffold is generic; real tools still need a packaging pass before they drop in cleanly.
- Maya 2025 currently emits a PySide/shiboken NumPy warning during UI-related imports. The build and smoke test still complete.
- The module assembly step still includes wheel metadata under the `scripts` payload. That can be cleaned up later.

## Docs

- [docs/maya-cython-pipeline-report.md](C:/PROJECTS/GG/gg_CythonCompile/docs/maya-cython-pipeline-report.md): research report and recommended architecture
- [docs/pipeline-quickstart.md](C:/PROJECTS/GG/gg_CythonCompile/docs/pipeline-quickstart.md): practical setup and usage guide

## Recommended next cleanup

- replace the scaffold package with the first real tracked tool package,
- split Python entrypoints from compiled implementation modules more cleanly,
- add Maya 2024 and Maya 2026 target configs,
- add install/uninstall scripts for local Maya module deployment,
- add `maya.standalone` tests in addition to the current import smoke test.
