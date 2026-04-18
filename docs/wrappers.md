---
summary: "PowerShell compatibility wrappers and their current interpreter fallback behavior."
read_when:
  - "When changing scripts/ wrappers."
  - "When debugging wrapper behavior versus direct CLI behavior."
---

# Wrappers

The repo still ships PowerShell entrypoints under [../scripts](../scripts), but they delegate into `maya_cython_compile` rather than owning pipeline logic themselves.

The four public wrappers share the internal helper [../scripts/_invoke-cli.ps1](../scripts/_invoke-cli.ps1) so interpreter fallback and CLI dispatch stay consistent in one place.

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
- forwards `-EnvPath` and `-MayaPy` only when that wrapper exposes them and you pass them explicitly
- forwards the matching safety flags as `-DryRun` and `-Force`
- dispatches into `python -m maya_cython_compile ...`

Current interpreter fallback order:

1. `<repoRoot>\<EnvPath>\python.exe` when `-EnvPath` is provided
2. `py -3`
3. `python`

If no interpreter is found, the wrapper throws.

## Wrapper defaults

Wrapper defaults now defer to the Python CLI and repo config:

- no wrapper forces a shared `env_path`
- no wrapper forces a `mayapy` value unless you pass one
- `assemble-module.ps1` no longer accepts `-MayaVersion` or `-ModuleName`; assembly always uses the selected target's `module_name` and `maya_version`
- `-Target <name>` is the normal way to select a named build target explicitly

Pass `-EnvPath` or `-MayaPy` only when you need to override the resolved config for that invocation.

For new behavior, change the Python CLI first, then keep the wrappers as thin delegates.
