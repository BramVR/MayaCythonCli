---
summary: "PowerShell compatibility wrappers and their current interpreter fallback behavior."
read_when:
  - "When changing scripts/ wrappers."
  - "When debugging wrapper behavior versus direct CLI behavior."
---

# Wrappers

The repo still ships PowerShell entrypoints under [../scripts](../scripts), but they delegate into `maya_cython_compile` rather than owning pipeline logic themselves.

## Available wrappers

- [../scripts/create-conda-env.ps1](../scripts/create-conda-env.ps1)
- [../scripts/build-package.ps1](../scripts/build-package.ps1)
- [../scripts/smoke-package.ps1](../scripts/smoke-package.ps1)
- [../scripts/assemble-module.ps1](../scripts/assemble-module.ps1)

## Current wrapper behavior

Each wrapper:

- resolves `repoRoot` from the script location
- sets `PYTHONPATH` to `<repoRoot>/src`
- forwards `-Target` to CLI `--target` when provided
- forwards the matching safety flags as `-DryRun` and `-Force`
- dispatches into `python -m maya_cython_compile ...`

Current interpreter fallback order:

1. `<repoRoot>\<EnvPath>\python.exe`
2. `py -3`
3. `python`

If no interpreter is found, the wrapper throws.

## Wrapper defaults

Current wrapper defaults match the script parameters, not a separate config layer:

- `create-conda-env.ps1`: `-EnvPath ".conda/maya-cython-build"`
- `build-package.ps1`: `-EnvPath ".conda/maya-cython-build"` and `-MayaPy "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe"`
- `smoke-package.ps1`: `-EnvPath ".conda/maya-cython-build"` and `-MayaPy "C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe"`
- `assemble-module.ps1`: `-EnvPath ".conda/maya-cython-build"`, `-ModuleName "MayaTool"`, and `-MayaVersion "2025"`

Use `-Target <name>` when you want a wrapper to select a named build target explicitly.

For new behavior, change the Python CLI first, then keep the wrappers as thin delegates.
