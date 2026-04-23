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

`environment.yml` is not part of either config layer, but it is still a required tracked input for any flow that needs `create-env`. Keep that file at `<repo-root>/environment.yml` in every repo that uses this pipeline.

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

For `conda_exe`, bare command names such as `conda` are resolved from `PATH` before any repo-relative fallback is considered.

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
| `conda_exe` | string | fallback Conda entrypoint path or command |
| `env_path` | path string | fallback local build env path |
| `maya_py` | path string | fallback `mayapy` executable |
| `targets` | object | per-target local path overrides |

Supported per-target keys under `targets.<name>`:

| Key | Type | Meaning |
| --- | --- | --- |
| `conda_exe` | string | target-specific Conda entrypoint path or command |
| `env_path` | path string | target-specific build env path |
| `maya_py` | path string | target-specific `mayapy` executable |

Example:

```json
{
  "target": "linux-2024",
  "conda_exe": "conda",
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
| `conda_exe` | `conda` from `PATH`, otherwise `%USERPROFILE%\anaconda3\condabin\conda.bat` on Windows |
| `env_path` | `.conda/<target>` |
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
| `python_version` | string | `"3.11"` |
| `package_data` | array of strings | `[]` |
| `smoke.callable` | string or null | `null` |
| `smoke.compiled_modules` | array of strings | `compiled_modules` |
| `smoke.resource_check` | string or null | `null` |
| `build_tree.source_mappings` | array | `[]` |
| `build_tree.rewrite_local_imports` | boolean | `false` |
| `build_tree.import_rewrites` | object | `{}` |

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
| `python_version` | string | target-specific Conda Python used to build the wheel |

Nested `smoke` config is merged, so target entries can override only the smoke keys they need.
Nested `build_tree` config is also merged, so target entries can override only the staging keys they need.

### `build_tree`

Use `build_tree` when the tracked repo is not already laid out as one clean Python package under `package_dir`.

Supported keys:

| Field | Type | Meaning |
| --- | --- | --- |
| `source_mappings` | array of objects | copy files or directories from the repo into the generated build tree before packaging |
| `rewrite_local_imports` | boolean | rewrite top-level sibling imports such as `import rig` into package-relative imports inside the staged package |
| `import_rewrites` | object | rewrite explicit import prefixes such as `from src import ui` into package-relative imports |

Supported `source_mappings[]` fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `source` | path string | repo-relative source file or directory to copy |
| `destination` | path string | destination path under the generated build root |
| `expand_children` | boolean | when `true` for a directory, copy that directory's children into `destination` instead of copying the directory itself |

If `source_mappings` is empty, the build tree keeps the old behavior and copies `package_dir` directly from the tracked repo.

Example for a repo with loose modules under `src/`, root-level `run.py`, and a desired packaged target at `src/curvenettool`:

```json
{
  "distribution_name": "curvenettool-maya",
  "package_name": "curvenettool",
  "package_dir": "src/curvenettool",
  "version": "0.1.0",
  "compiled_modules": ["bifrost_deformer", "data", "maya_utils", "network", "rig", "ui"],
  "package_data": ["resources/*", "run.py"],
  "smoke": {
    "compiled_modules": ["bifrost_deformer", "data", "maya_utils", "network", "rig", "ui"],
    "resource_check": "resources/main_control.json"
  },
  "build_tree": {
    "source_mappings": [
      {
        "source": "src",
        "destination": "src/curvenettool",
        "expand_children": true
      },
      {
        "source": "run.py",
        "destination": "src/curvenettool/run.py"
      }
    ],
    "rewrite_local_imports": true,
    "import_rewrites": {
      "src": "."
    }
  }
}
```

That pattern is meant for repos that are importable in Maya only because their source root is injected directly into `sys.path`. After staging, the generated package becomes importable as `curvenettool.*`, while sibling imports such as `import rig` and explicit legacy imports such as `from src import ui` are rewritten into package-relative imports inside the build tree.

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
  "build_tree": {
    "source_mappings": [],
    "rewrite_local_imports": false,
    "import_rewrites": {}
  },
  "default_target": "windows-2025",
  "targets": {
    "windows-2025": {
      "platform": "windows",
      "module_name": "MayaTool",
      "maya_version": "2025",
      "python_version": "3.11"
    },
    "linux-2024": {
      "platform": "linux",
      "module_name": "MayaToolLinux",
      "maya_version": "2024",
      "python_version": "3.10"
    }
  }
}
```

## Migration path

Safe migration from the old single-target file:

1. Keep the existing top-level shared fields.
2. Move target-specific fields such as `platform`, `module_name`, `maya_version`, and `python_version` into `targets.<name>`.
3. Add `default_target`.
4. Add optional `.maya-cython-compile.json.target` and `.maya-cython-compile.json.targets.<name>` overrides when one machine switches between multiple targets.

Flat legacy configs continue to work until you migrate.
