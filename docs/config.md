---
summary: "Repo-local config location, precedence, and build-config schema."
read_when:
  - "When adding config keys or changing default paths."
  - "When updating build-config.json or config precedence."
---

# Config

`maya-cython-compile` resolves two config layers:

- tracked repo metadata from `build-config.json`
- optional repo-local machine paths from `.maya-cython-compile.json`

## Precedence

For local path settings:

1. CLI flags
2. Environment variables
3. Repo-local config file
4. Built-in defaults

Relative paths from flags, env vars, or `.maya-cython-compile.json` resolve relative to `repo_root`.

## Local config location

Default path:

- `<repo-root>/.maya-cython-compile.json`

If `--config PATH` is provided, the CLI reads that exact file instead.

There is no user-level or system-level config discovery. The current implementation does not search home-directory dotfiles, XDG paths, or `%APPDATA%`.

## Local config schema

Supported keys:

| Key | Type | Meaning |
| --- | --- | --- |
| `conda_exe` | path string | Conda entrypoint |
| `env_path` | path string | local build env path |
| `maya_py` | path string | `mayapy` executable |

Example:

```json
{
  "conda_exe": "C:/Users/me/anaconda3/condabin/conda.bat",
  "env_path": ".conda/maya-cython-build",
  "maya_py": "C:/Program Files/Autodesk/Maya2025/bin/mayapy.exe"
}
```

## Environment variables

| Variable | Meaning |
| --- | --- |
| `MAYA_CYTHON_COMPILE_CONDA_EXE` | overrides `conda_exe` |
| `MAYA_CYTHON_COMPILE_ENV_PATH` | overrides `env_path` |
| `MAYA_CYTHON_COMPILE_MAYA_PY` | overrides `maya_py` |

## Built-in defaults

| Setting | Default |
| --- | --- |
| `conda_exe` | `%USERPROFILE%\anaconda3\condabin\conda.bat` |
| `env_path` | `.conda/maya-cython-build` |
| `maya_py` | `C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe` |

## `build-config.json`

Tracked build metadata must live at [../build-config.json](../build-config.json).

Required fields:

| Field | Type |
| --- | --- |
| `distribution_name` | string |
| `package_name` | string |
| `package_dir` | string |
| `version` | string |
| `compiled_modules` | array of strings |

Optional fields:

| Field | Type | Default |
| --- | --- | --- |
| `module_name` | string | `package_name` |
| `maya_version` | string or number | `"2025"` |
| `package_data` | array of strings | `[]` |
| `smoke.callable` | string or null | `null` |
| `smoke.compiled_modules` | array of strings | `compiled_modules` |
| `smoke.resource_check` | string or null | `null` |

Current repo example:

```json
{
  "distribution_name": "maya-tool",
  "package_name": "maya_tool",
  "package_dir": "src/maya_tool",
  "module_name": "MayaTool",
  "maya_version": "2025",
  "version": "0.1.0",
  "compiled_modules": ["_cy_logic"],
  "package_data": ["*.json"],
  "smoke": {
    "callable": "show_ui",
    "compiled_modules": ["_cy_logic"],
    "resource_check": "tool_manifest.json"
  }
}
```
