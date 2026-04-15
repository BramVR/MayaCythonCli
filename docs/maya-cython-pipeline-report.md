# Maya + Cython Pipeline Research Report

Date: 2026-04-15

## Bottom line

Yes, this is a sensible pipeline.

The cleanest approach for Maya is:

1. Keep your Maya-facing entrypoints in normal Python.
2. Compile selected internal modules to Cython extension modules (`.pyd` on Windows, `.so` on Linux/macOS).
3. Build per Maya Python version and platform.
4. Distribute the result as a Maya module package (`.mod` + `scripts/`, `plug-ins/`, `icons/`) instead of copying files into the Maya install.
5. Use `mayapy` for package management and smoke tests, and `maya.standalone.initialize()` for non-GUI integration tests.

That gives you a workable mix of speed, source obfuscation, predictable deployment, and version control over Maya-specific builds.

## What matters technically

### 1. The real compatibility boundary is Maya's embedded Python

For Cython, the important target is not just "Maya 2025" or "Maya 2026". The main boundary is the CPython version bundled inside Maya.

Recent Autodesk docs show:

| Maya version | Embedded Python |
| --- | --- |
| 2024 | 3.10.8 |
| 2025 | 3.11.4 |
| 2026 | 3.11.4 |

Implication:

- Maya 2024 needs a `cp310` build.
- Maya 2025 and 2026 both target `cp311`.
- Even when two Maya versions share the same Python version, you should still test both before treating them as one deployment target.

### 2. What Cython actually produces

Cython does not "encrypt Python". It translates `.pyx` or supported `.py` code to C/C++, then compiles that to a Python extension module.

Practical implications:

- Target machines do not need Cython installed.
- Target machines do need a binary built for the correct Python ABI and OS/platform.
- On Windows, the compiled artifact is a `.pyd`.
- You will rebuild for each supported platform and, usually, each Python minor version.

### 3. Maya already supports a packaging flow you can build on

Autodesk's module system is the right deployment boundary.

Why it fits:

- A `.mod` file can select different payloads by Maya version and platform.
- Maya adds a module's `scripts` path to both `MAYA_SCRIPT_PATH` and `PYTHONPATH`.
- That means compiled Python extension modules can live inside the module's `scripts` tree and be imported normally.
- This is safer than copying files into the Maya installation.

### 4. `mayapy` should be part of the build/test loop

Autodesk documents `mayapy` as Maya's bundled Python interpreter and supports `pip` through it.

That matters because:

- it gives you the interpreter Maya actually uses,
- it can install dependencies into version-specific script locations,
- it is the most reliable place to run smoke tests for imports and runtime behavior.

## Recommended architecture

### Keep two layers

Use this split:

- Python layer:
  - UI
  - shelf commands
  - menu bootstrapping
  - scene/tool orchestration
  - stable public API for your studio tools
- Cython layer:
  - heavy loops
  - geometry/math helpers
  - data transforms
  - internal logic you want to ship as compiled binaries

This is the important design decision.

Do **not** Cython-compile your whole Maya toolset on day one.

Reasons:

- Maya tool entrypoints are easier to debug in plain Python.
- startup/bootstrap code is better kept human-readable,
- traceback quality and iteration speed stay better,
- compiled modules should be the replaceable implementation detail, not the user-facing contract.

### Recommended package shape

Suggested source layout:

```text
repo/
  pyproject.toml
  src/
    gg_maya_tool/
      __init__.py
      bootstrap.py
      commands.py
      api.py
      _cy/
        mesh_ops.pyx
        deform_math.pyx
        fast_lookup.pyx
  tests/
    test_api.py
    test_standalone_smoke.py
  scripts/
    build-wheel.ps1
    assemble-module.ps1
    smoke-mayapy.ps1
    smoke-standalone.ps1
  maya_module/
    gg_maya_tool.mod.in
```

Rules:

- `gg_maya_tool.bootstrap` stays Python.
- `gg_maya_tool._cy.*` contains the compiled modules.
- Public code imports from `_cy` behind small Python wrappers when needed.
- Nothing in Maya startup paths imports deep Cython internals directly.

### Recommended build backend

For v1, use `setuptools` + `Cython` + `pyproject.toml`.

Reason:

- It is the documented/default path in both Cython and setuptools.
- It is enough for `.pyx` to extension-module workflows.
- You do not need a heavier native build system unless you start linking extra C/C++ libraries.

`python -m build` is a good frontend for generating wheels once the project is set up.

## Deployment options compared

### Option A: build in place and copy `.pyd` files around

Pros:

- fastest to prototype,
- simple local testing.

Cons:

- messy,
- weak version tracking,
- easy to deploy the wrong binary,
- no clean artifact story.

Verdict:

- acceptable only for early local experiments.

### Option B: build wheel(s), then install with `mayapy`

Pros:

- normal Python packaging workflow,
- versioned artifacts,
- easy to automate,
- works well for developer installs.

Cons:

- not a full studio deployment story on its own,
- artists still need a controlled install target.

Verdict:

- good as the internal build artifact.

### Option C: build wheel(s), then assemble a Maya module package

Pros:

- best fit for studio deployment,
- clean separation by Maya version/platform,
- works with shared locations and controlled rollout,
- matches Autodesk's intended add-on distribution model.

Cons:

- one extra assembly step,
- slightly more structure to maintain.

Verdict:

- recommended.

## Recommended pipeline

### Local developer loop

For a single Maya target:

1. Work in the source repo.
2. Build the extension modules for the target Maya/Python version.
3. Run smoke tests under `mayapy`.
4. Run a standalone Maya API smoke test with `maya.standalone.initialize()`.
5. Install or sync the artifact to the developer's Maya module path.

For local developer installs, Autodesk supports:

- `mayapy -m pip install --user ...`
- `mayapy -m pip install --target <maya-version-specific scripts path> ...`

My recommendation:

- Use `--target` for disposable local installs.
- Use a module package for anything shared or repeatable.

### CI or build-farm loop

For each target in the build matrix:

1. Select target:
   - Maya 2024 / Windows / CPython 3.10
   - Maya 2025 / Windows / CPython 3.11
   - Maya 2026 / Windows / CPython 3.11
   - plus Linux/macOS variants only if your studio actually supports them
2. Install build dependencies into that target interpreter/toolchain.
3. Build the wheel.
4. Run import smoke tests under `mayapy`.
5. Run standalone API smoke tests.
6. Assemble a Maya module package containing the wheel contents or unpacked package tree.
7. Publish versioned artifacts.

Recommended outputs:

- `dist/wheels/...whl`
- `dist/module/<maya-version>/<platform>/...`
- `dist/release/<tool>-<version>-maya2026-win64.zip`

### Runtime deployment

Use a `.mod` file plus version/platform-specific module roots.

Example strategy:

- one module file,
- one module root per Maya major version and platform,
- identical Python entrypoints where possible,
- version-specific compiled binaries where required.

Autodesk's module system supports:

- `MAYAVERSION`
- `PLATFORM`
- script path overrides
- relative environment variable paths

That is enough to keep one studio-facing package while still routing Maya 2024 to `cp310` builds and Maya 2025/2026 to `cp311` builds.

## Important recommendation: treat 2025 and 2026 as "same binary candidate", not "guaranteed same target"

Because Autodesk documents Python 3.11.4 in both Maya 2025 and 2026, a plain CPython extension module may be reusable across those two versions on the same OS/arch.

But I would still structure the pipeline as if they are separate targets until proven otherwise.

Why:

- Autodesk can change bundled libraries and surrounding runtime details.
- You may later add Maya-version-specific Python code around the compiled layer.
- Keeping the artifact layout version-aware now avoids repainting the pipeline later.

Practical compromise:

- build separate `maya2025` and `maya2026` artifacts,
- if validation shows the compiled payload is identical, let the assembly step reuse the same wheel internally.

## Build-system specifics

### Use `pyproject.toml`

Recommended build dependencies:

- `setuptools`
- `cython`
- `build`
- `wheel`

Use `setuptools.Extension` for compiled modules.

This is the most conventional and least risky path.

### Use `mayapy` for validation even if you build elsewhere

Inference:

- A stock CPython 3.11 build environment can often produce a valid `cp311` extension for Maya 2025/2026.
- But the safest validation point is still `mayapy`, because it exercises the actual embedded interpreter environment Maya ships.

If you want the lowest-risk pipeline, build and test with Maya installed on the build machine.

### Use `maya.standalone` for integration tests

For non-GUI testing, Autodesk supports initializing Maya libraries from external Python with:

```python
import maya.standalone
maya.standalone.initialize()
...
maya.standalone.uninitialize()
```

That is the right place to validate:

- importability of your compiled modules,
- access to `maya.cmds`,
- basic API calls,
- simple scene operations.

## What not to do

### 1. Do not install into the Maya program directory

Autodesk explicitly documents safer alternatives:

- module packages,
- user installs,
- version-specific script paths.

Writing into the Maya installation is harder to maintain and easier to break.

### 2. Do not rely on global `PYTHONPATH` as the main deployment mechanism

`Maya.env` is useful for local setup and can define `MAYA_MODULE_PATH`, but Autodesk also documents that normal OS environment variables usually take precedence over `Maya.env` values.

For a studio pipeline, module packages are the cleaner source of truth.

### 3. Do not start with Cython limited-API / `abi3` as the primary strategy

Python and setuptools support the stable ABI / limited API path.

Cython also documents Limited API support from 3.1 onward, but with caveats:

- missing features,
- bugs still possible,
- performance cost,
- explicit cross-version testing still required.

Conclusion:

- it is interesting later,
- it is not the safest v1 plan for Maya tools.

### 4. Do not recursively scan script trees unless you actually need it

Maya modules can recursively scan folder overrides, but Autodesk documents limitations and ignored folder/file patterns in recursive mode.

You usually do not need recursive module scanning for Python packages anyway:

- put the package root on `PYTHONPATH`,
- let Python package imports handle the rest.

## Suggested first implementation plan

### Phase 1: prove the concept

Goal:

- compile one small internal module,
- import it from Maya,
- call it from a Python wrapper.

Deliverables:

- `pyproject.toml`
- one `.pyx` module
- one plain Python wrapper
- one `mayapy` smoke test
- one simple `.mod` package layout

### Phase 2: turn it into a repeatable build

Add:

- PowerShell build scripts,
- target matrix configuration,
- module assembly script,
- versioned output folders.

### Phase 3: validate real studio use

Add:

- Maya 2024/2025/2026 test coverage as needed,
- shared deployment location,
- install/update instructions,
- rollback story,
- dependency pinning.

## Concrete recommendation for this repo

If this repo is intended to become the pipeline repo, I would build it around this contract:

1. Source lives under `src/`.
2. Compiled code lives under `src/<package>/_cy/`.
3. Public Maya entrypoints remain Python.
4. Wheels are the primary build artifact.
5. Maya module packages are the primary deployment artifact.
6. `mayapy` smoke tests are mandatory for every target.
7. Support matrix starts with Windows only unless you already know Linux/macOS matter.
8. Treat Maya 2024 as `cp310`, and Maya 2025/2026 as `cp311`.

If the goal is "easy way to make Cython files for Maya", this is the shortest path that will still scale into a real studio pipeline instead of becoming a pile of copied `.pyd` files.

## Risks and limits

### Reverse engineering / IP protection

Cython improves source hiding, but it is not strong protection.

- determined users can still inspect binaries,
- Python-visible names and behavior still leak information,
- secrets should not live in client-side compiled code.

### Debuggability

Compiled modules make debugging slower than plain Python.

Mitigation:

- keep wrappers in Python,
- compile only internals,
- keep a pure-Python fallback path during early rollout if needed.

### Multi-version maintenance

Supporting several Maya versions means supporting several binary targets.

Mitigation:

- explicit build matrix,
- explicit artifact naming,
- explicit smoke tests.

## Source links

Autodesk:

- Maya 2024 Open Source Components: https://help.autodesk.com/cloudhelp/2024/CHS/Maya-SDK/files/Open-Source-Components/Maya_SDK_Open_Source_Components_2024_Open_Source_Components_html.html
- Maya 2025 Open Source Components: https://help.autodesk.com/cloudhelp/2025/ENU/Maya-DEVHELP/files/Maya_DEVHELP_Open_Source_Components_html.html
- Maya 2026 Open Source Components: https://help.autodesk.com/cloudhelp/2026/ENU/Maya-DEVHELP/files/Maya_DEVHELP_Open_Source_Components_html.html
- Python in Maya: https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Scripting/files/GUID-C0F27A50-3DD6-454C-A4D1-9E3C44B3C990.htm
- Managing Python packages with mayapy and pip: https://help.autodesk.com/cloudhelp/2025/ENU/Maya-Scripting/files/GUID-72A245EC-CDB4-46AB-BEE0-4BBBF9791627.htm
- Running Python scripts outside a Maya session: https://help.autodesk.com/cloudhelp/2026/ENU/Maya-DEVHELP/files/Maya-Python-API/Maya_DEVHELP_Maya_Python_API_PythonOutsideMayaSession_html.html
- Running venv with mayapy: https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Scripting/files/GUID-6AF99E9C-1473-481E-A144-357577A53717.htm
- Module description files: https://help.autodesk.com/cloudhelp/2025/ENU/Maya-DEVHELP/files/Distributing-Maya-Plug-ins/DistributingUsingModules/Maya_DEVHELP_Distributing_Maya_Plug_ins_DistributingUsingModules_ModuleDescriptionFiles_html.html
- Installing the module: https://help.autodesk.com/cloudhelp/2024/CHS/Maya-SDK/files/Distributing-Maya-Plug-ins/DistributingUsingModules/Maya_SDK_Distributing_Maya_Plug_ins_DistributingUsingModules_InstallingModules_html.html
- Setting environment variables using Maya.env: https://help.autodesk.com/view/MAYAUL/2026/ENU/?guid=GUID-8EFB1AC1-ED7D-4099-9EEE-624097872C04

Python packaging / Cython:

- Cython build quickstart: https://docs.cython.org/en/stable/src/quickstart/build.html
- Cython source files and compilation: https://docs.cython.org/src/userguide/source_files_and_compilation.html
- Setuptools extension modules: https://setuptools.pypa.io/en/stable/userguide/ext_modules.html
- Python Stable ABI / Limited API: https://docs.python.org/3.12/c-api/stable.html
- Python packaging compatibility tags: https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/
- `build` frontend docs: https://build.pypa.io/en/latest/

## My recommendation in one sentence

Build Cython extensions as normal Python wheels, validate them with `mayapy`, and ship them to Maya through version-aware `.mod` packages rather than direct file copying or global `PYTHONPATH` hacks.
