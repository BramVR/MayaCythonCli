---
summary: "Repo-local config location, precedence, and build-config schema."
read_when:
  - "When adding config keys or changing default paths."
  - "When updating build-config.json or config precedence."
---

# Config

`maya-cython-compile` resolves two config layers:

- tracked build metadata from `build-config.json`
- optional repo-local machine paths from `.maya-cython-compile.json`

The selected target can come from either layer.

## Target selection precedence

1. CLI `--target`
2. `MAYA_CYTHON_COMPILE_TARGET`
3. `.maya-cython-compile.json` `target`
4. `build-config.json` `default_target`
5. the only entry in `build-config.json.targets`
6. legacy flat `build-config.json`, exposed as the implicit target `default`

## Local path precedence

For local path settings:

1. CLI flags
2. Environment variables
3. Repo-local target override under `.maya-cython-compile.json.targets.<name>`
4. Repo-local top-level settings in `.maya-cython-compile.json`
5. Built-in defaults

Relative paths from flags, env vars, or `.maya-cython-compile.json` resolve relative to `repo_root`.

## Local config location

Default path:

- `<repo-root>/.maya-cython-compile.json`

If `--config PATH` is provided, the CLI reads that exact file instead.

There is no user-level or system-level config discovery. The current implementation does not search home-directory dotfiles, XDG paths, or `%APPDATA%`.

## Local config schema

Supported top-level keys:

| Key | Type | Meaning |
| --- | --- | --- |
| `target` | string | default named target for this machine |
| `conda_exe` | path string | fallback Conda entrypoint |
| `env_path` | path string | fallback local build env path |
| `maya_py` | path string | fallback `mayapy` executable |
| `targets` | object | per-target local path overrides |

Supported per-target keys under `targets.<name>`:

| Key | Type | Meaning |
| --- | --- | --- |
| `conda_exe` | path string | target-specific Conda entrypoint |
| `env_path` | path string | target-specific build env path |
| `maya_py` | path string | target-specific `mayapy` executable |

Example:

```json
{
  "target": "linux-2024",
  "conda_exe": "C:/Users/me/anaconda3/condabin/conda.bat",
  "targets": {
    "windows-2025": {
      "env_path": ".conda/windows-2025",
      "maya_py": "C:/Program Files/Autodesk/Maya2025/bin/mayapy.exe"
    },
    "linux-2024": {
      "env_path": ".conda/linux-2024",
      "maya_py": "/usr/autodesk/maya2024/bin/mayapy"
    }
  }
}
```

## Environment variables

| Variable | Meaning |
| --- | --- |
| `MAYA_CYTHON_COMPILE_TARGET` | overrides the selected target |
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

### Legacy single-target schema

Legacy flat configs still work. They are treated as the implicit target `default` with platform `windows`.

Legacy required fields:

| Field | Type |
| --- | --- |
| `distribution_name` | string |
| `package_name` | string |
| `package_dir` | string |
| `version` | string |
| `compiled_modules` | array of strings |

Legacy optional fields:

| Field | Type | Default |
| --- | --- | --- |
| `module_name` | string | `package_name` |
| `maya_version` | string or number | `"2025"` |
| `package_data` | array of strings | `[]` |
| `smoke.callable` | string or null | `null` |
| `smoke.compiled_modules` | array of strings | `compiled_modules` |
| `smoke.resource_check` | string or null | `null` |

### Named target schema

The preferred schema keeps shared build fields at the top level and adds:

| Field | Type | Meaning |
| --- | --- | --- |
| `default_target` | string | repo default named target |
| `targets` | object | named target overrides merged onto the top level |

Each target entry may override any tracked build field. Common cases are:

| Target Field | Type | Meaning |
| --- | --- | --- |
| `platform` | string | target platform, normalized from `windows`, `linux`, or `macos` aliases |
| `module_name` | string | target-specific Maya module name |
| `maya_version` | string or number | target-specific Maya version |

Nested `smoke` config is merged, so target entries can override only the smoke keys they need.

Current repo example:

```json
{
  "distribution_name": "maya-tool",
  "package_name": "maya_tool",
  "package_dir": "src/maya_tool",
  "version": "0.1.0",
  "compiled_modules": ["_cy_logic"],
  "package_data": ["*.json"],
  "smoke": {
    "callable": "show_ui",
    "compiled_modules": ["_cy_logic"],
    "resource_check": "tool_manifest.json"
  },
  "default_target": "windows-2025",
  "targets": {
    "windows-2025": {
      "platform": "windows",
      "module_name": "MayaTool",
      "maya_version": "2025"
    },
    "linux-2024": {
      "platform": "linux",
      "module_name": "MayaToolLinux",
      "maya_version": "2024"
    }
  }
}
```

## Migration path

Safe migration from the old single-target file:

1. Keep the existing top-level shared fields.
2. Move target-specific fields such as `platform`, `module_name`, and `maya_version` into `targets.<name>`.
3. Add `default_target`.
4. Add optional `.maya-cython-compile.json.target` and `.maya-cython-compile.json.targets.<name>` overrides when one machine switches between multiple targets.

Flat legacy configs continue to work until you migrate.
