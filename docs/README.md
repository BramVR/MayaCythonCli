---
summary: "Docs index with short descriptions for the main Maya Cython compile topics."
---

# Docs

- [quickstart.md](quickstart.md) - first-run setup and the normal build, smoke, and assemble flow
- [cli.md](cli.md) - command surface, flags, JSON and text output, and exit codes
- [config.md](config.md) - config file location, precedence, and `build-config.json` schema
- [architecture.md](architecture.md) - why the CLI owns orchestration and how the build tree is assembled
- [wrappers.md](wrappers.md) - PowerShell compatibility wrappers and their current interpreter fallback behavior
- [testing.md](testing.md) - repo-local lint, type-check, and test commands

Current defaults:

- platform: Windows
- Maya version: `2025`
- target package: `src/maya_tool`
- repo-local config file: `<repo-root>/.maya-cython-compile.json`
