---
summary: "Docs index with short descriptions for the main Maya Cython compile topics."
read_when:
  - "When you want a quick doc map with one-line descriptions before reading deeper pages."
  - "When updating docs navigation or checking whether a topic already has a page."
---

# Docs

- [quickstart.md](quickstart.md) - first-run setup and the normal build, smoke, and assemble flow
- [cli.md](cli.md) - command surface, flags, JSON and text output, and exit codes
- [config.md](config.md) - config file location, precedence, and `build-config.json` schema
- [architecture.md](architecture.md) - why the CLI owns orchestration and how target-scoped build outputs are assembled
- [wrappers.md](wrappers.md) - PowerShell compatibility wrappers and their current interpreter fallback behavior
- [testing.md](testing.md) - repo-local lint, type-check, and test commands

Current defaults:

- default target: `windows-2025`
- platform: Windows
- Maya version: `2025`
- target package: `src/maya_tool`
- repo-local config file: `<repo-root>/.maya-cython-compile.json`
