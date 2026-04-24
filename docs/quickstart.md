---
summary: "First-run setup and the normal create-env, build, smoke, and assemble flow."
read_when:
  - "When setting up the repo on a new Windows machine."
  - "When you need the shortest safe path through the pipeline."
---

# Quickstart

Build a Maya-targeted Cython wheel from a normal Python environment, validate it under `mayapy`, then assemble a Maya module layout from the built wheel.
Package the assembled Maya module root into a release zip when you need something end users can install directly.

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

The PowerShell wrappers in [wrappers.md](wrappers.md) can still be used on Windows if you do not want to install the CLI globally. They stay thin delegates over the Python CLI, so use `-Target` instead of expecting wrapper-specific Maya version or platform defaults.

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
- the resolved Python include path and Python library metadata, with fallback to standard Maya and Python runtime include and library layouts when `mayapy` leaves those paths blank or points at missing directories

## Minimum tracked inputs per repo

Every repo you build through this CLI needs these tracked inputs at its own repo root:

- `build-config.json`
- `environment.yml`

And usually this untracked machine-local file:

- `.maya-cython-compile.json`

`doctor` and `verify --scenario target-dry-run` can still succeed before the env file exists, because they only validate config and preview commands. `create-env` and any flow that reaches it, including `verify --scenario target-run`, require `<repo-root>/environment.yml`.

## Adopting an existing Maya repo

For a fresh external repo:

1. Add `build-config.json` with the target package name, compiled modules, smoke settings, and targets.
2. Add `environment.yml` with the Conda and pip dependencies needed to build the wheel.
3. Add `.maya-cython-compile.json` with machine-local `conda_exe`, `env_path`, and `maya_py` overrides when the defaults are not enough.
4. Run `maya-cython-compile --target windows-2025 verify --scenario target-dry-run --json`.
5. Fix config or path issues first.
6. Promote to `maya-cython-compile --target windows-2025 verify --scenario target-run --json --json-errors`.

If the external repo is not already one clean Python package under `package_dir`, stage it into one with `build_tree.source_mappings` and import rewrites before the wheel build starts.

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
- probes `mayapy` directly for Python include and library metadata, with fallback discovery for standard Maya and Python runtime include and library layouts when needed
- rejects a selected target when its platform or Python version does not match the probed `mayapy` runtime
- cleans prior target-scoped build artifacts when `--force` allows it
- prepares `build/target-build/<target>/`
- stages the package contents into that build tree, either by copying `package_dir` directly or by applying optional `build_tree.source_mappings` first
- rejects source mappings that resolve outside the repo root or destination mappings that resolve outside the generated build root
- can rewrite package-local imports inside the staged tree when `build_tree.rewrite_local_imports` or `build_tree.import_rewrites` is configured
- uses repo-relative extension source paths inside the generated build tree so Windows wheel builds do not trip over duplicated absolute temp paths
- writes a generated `pyproject.toml` plus `setup.py` into that target build tree
- runs `python -m build --wheel --no-isolation` inside the configured Conda env
- writes the wheel to `dist/<target>/`
- writes `dist/<target>/artifact.json`, which records the exact wheel selected for that target plus its `sha256`

## Smoke the wheel under Maya

```powershell
maya-cython-compile --target windows-2025 smoke --dry-run
maya-cython-compile --target windows-2025 smoke --force
```

The smoke step resolves `dist/<target>/artifact.json`, verifies the referenced wheel hash, checks that the wheel's `.dist-info` target metadata matches the selected target, safely extracts it to `build/smoke/<target>/wheel/`, sets `PYTHONPATH` to that extraction root, and validates the configured imports, callable, and resource check under `mayapy`. If the manifest is missing or the wheel metadata does not match, rebuild that target first.

`mayapy` can still emit runtime warnings during a successful smoke run. Treat the step as passed when the command exits `0` and the configured smoke checks succeed; inspect the smoke logs if you need to distinguish a Maya warning from a packaging failure.

## Assemble the Maya module

```powershell
maya-cython-compile --target windows-2025 assemble --dry-run
maya-cython-compile --target windows-2025 assemble --force
```

Expected outputs:

- `dist/<target>/artifact.json`
- `dist/module/<target>/<ModuleName>/<ModuleName>.mod`
- `dist/module/<target>/<ModuleName>/contents/scripts/<package>/`

The assembled `.mod` file now derives its module name, `MAYAVERSION:`, and `PLATFORM:` from the selected target. If you reuse one module name across multiple Maya versions or operating systems, the target-scoped `dist/module/<target>/...` layout keeps those assembled outputs separate.

## Package a release zip

```powershell
maya-cython-compile --target windows-2025 package --dry-run
maya-cython-compile --target windows-2025 package --force
```

Expected outputs:

- `dist/release/<target>/<ModuleName>-<version>-maya<MayaVersion>-<platform>.zip`

The release zip is the artifact you should hand to end users. It contains one top-level `<ModuleName>/` folder with:

- `<ModuleName>.mod`
- `contents/`
- `INSTALL.txt`

The wheel under `dist/<target>/` is still the pipeline's intermediate build artifact. End users normally should not install that wheel directly.

## Run the full flow

```powershell
maya-cython-compile --target windows-2025 run --dry-run
maya-cython-compile --target windows-2025 run --dry-run --ensure-env
maya-cython-compile --target windows-2025 run --ensure-env --force
```

Useful variants:

```powershell
maya-cython-compile --target windows-2025 run --skip-smoke
maya-cython-compile --target windows-2025 run --skip-assemble
maya-cython-compile --target windows-2025 run --skip-package
maya-cython-compile --target windows-2025 run --force
```

Windows wrapper equivalents:

```powershell
.\scripts\run-pipeline.ps1 -Target windows-2025 -DryRun
.\scripts\run-pipeline.ps1 -Target windows-2025 -EnsureEnv -Force
```

Sharing one Conda env across multiple targets is only safe when those targets use the same Python ABI and compatible build dependencies. The default `.conda/<target>` layout avoids cross-target wheel and interpreter drift.

## End-user install

For the normal Maya user workflow:

1. Give the user the release zip from `dist/release/<target>/`.
2. They extract it into a folder already covered by `MAYA_MODULE_PATH`, or into a shared studio modules location.
3. They start Maya.
4. They run the package entrypoint from Maya Python, for example `import maya_tool; maya_tool.show_ui()`.

## Non-interactive contract

- the CLI does not prompt
- the CLI does not read from stdin
- destructive cleanup is blocked unless `--force` is provided
- `--dry-run` previews deletions and subprocesses without changing files
- Ctrl-C is normalized to `Interrupted.` with exit code `130`

## For a real tool

Replace [../src/maya_tool](../src/maya_tool) with the package you want to ship, then update [../build-config.json](../build-config.json) so the pipeline compiles and assembles the correct target or set of targets.

If the source repo is not already arranged as one package under `package_dir`, keep `package_dir` as the desired packaged destination and use `build_tree.source_mappings` plus optional import rewrites to stage loose modules, resource folders, or root scripts into the generated build tree before the wheel build starts.

One common case is a flat Maya tool repo with loose modules under `src/`, resource files under `src/resources/`, and a root `run.py`. In that case:

- set `package_dir` to the packaged destination you want, such as `src/curvenettool`
- map the loose `src/` children into that package with `build_tree.source_mappings`
- map root launch scripts such as `run.py` into the package if you want them shipped
- enable `rewrite_local_imports` for sibling imports such as `import rig`
- add `import_rewrites` entries for explicit prefixes such as `from src import ui`

This pattern has been validated against a real flat-layout Maya tool for a Windows Maya 2025 target. The full `verify --scenario target-run` flow built CPython 3.11 Windows extensions, smoked them under Maya `mayapy`, assembled the Maya module, and produced the target-scoped release zip.
