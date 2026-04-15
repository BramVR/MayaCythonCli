# maya-cython-compile

Windows-first CLI for building Maya Python tools into Maya-compatible Cython extension packages.

## What it does

This repo now treats the build pipeline as a CLI instead of a set of ad-hoc scripts.

The default flow is:

1. create a local Conda build env
2. compile the configured package against Maya's Python headers/libs
3. smoke-test the built wheel under `mayapy`
4. assemble a `.mod`-based Maya module layout

The build happens from a normal Python environment. `mayapy` is only used for runtime validation.

## Commands

After installing the repo in editable mode:

```powershell
pip install -e .
maya-cython-compile doctor
maya-cython-compile create-env
maya-cython-compile build
maya-cython-compile smoke
maya-cython-compile assemble
maya-cython-compile run --ensure-env
```

If you do not want to install it yet, the PowerShell wrappers in [scripts](scripts) still work and now delegate into the CLI.

## Quick start

Prereqs:

- Autodesk Maya installed locally
- Anaconda or Miniconda installed locally
- Visual Studio C++ build tools available

Inspect the resolved paths first:

```powershell
maya-cython-compile doctor
```

Create the build env:

```powershell
maya-cython-compile create-env
```

Build the wheel:

```powershell
maya-cython-compile build
```

Smoke test under Maya:

```powershell
maya-cython-compile smoke
```

Assemble the Maya module layout:

```powershell
maya-cython-compile assemble
```

Run the whole pipeline:

```powershell
maya-cython-compile run --ensure-env
```

## Config

Tracked build metadata lives in [build-config.json](build-config.json).

Optional local machine overrides can live in `.maya-cython-compile.json` at the repo root:

```json
{
  "conda_exe": "C:/Users/you/anaconda3/condabin/conda.bat",
  "env_path": ".conda/maya-cython-build",
  "maya_py": "C:/Program Files/Autodesk/Maya2025/bin/mayapy.exe"
}
```

Precedence is:

1. CLI flags
2. environment variables
3. `.maya-cython-compile.json`
4. built-in defaults

Environment variable overrides:

- `MAYA_CYTHON_COMPILE_CONDA_EXE`
- `MAYA_CYTHON_COMPILE_ENV_PATH`
- `MAYA_CYTHON_COMPILE_MAYA_PY`

Show the resolved config:

```powershell
maya-cython-compile config show --json
```

## Current scaffold target

Validated target:

- Windows
- Autodesk Maya 2025
- CPython 3.11 (`cp311`)

The current sample target package is [src/maya_tool](src/maya_tool).

## Key files

- [pyproject.toml](pyproject.toml): CLI packaging and console entrypoint
- [build-config.json](build-config.json): tracked target build metadata
- [environment.yml](environment.yml): Conda build environment
- [src/maya_cython_compile](src/maya_cython_compile): CLI/config/pipeline implementation
- [src/maya_tool](src/maya_tool): sample Maya package scaffold used as build input
- [scripts](scripts): compatibility wrappers that delegate into the CLI
- [docs/pipeline-quickstart.md](docs/pipeline-quickstart.md): practical setup and usage guide

## Outputs

- wheels are written to `dist/`
- smoke extraction goes to `build/smoke/`
- assembled Maya modules go to `dist/module/`

## Notes

- The scaffold is still generic; a real production tool package should replace `src/maya_tool`.
- Maya 2025 may still emit a PySide/shiboken NumPy warning during UI-related imports.
- Module assembly now skips wheel metadata directories when unpacking into `contents/scripts`.
