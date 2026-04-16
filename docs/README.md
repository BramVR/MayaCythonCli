# Documentation

Date: 2026-04-15

This repo is now centered around the `maya-cython-compile` CLI. The docs in this folder are the canonical reference for how the pipeline works, how it is configured, and why it is structured this way.

Start here:

- [Pipeline Quickstart](./pipeline-quickstart.md): first-time setup and the normal build flow
- [CLI Reference](./cli-reference.md): commands, flags, outputs, and compatibility wrappers
- [Architecture](./architecture.md): package split, build flow, and why the CLI owns orchestration

Current defaults:

- platform: Windows
- Maya version: 2025
- target package: `src/maya_tool`
- local config file: `<repo-root>/.maya-cython-compile.json`

Core tracked inputs:

- [../build-config.json](../build-config.json)
- [../environment.yml](../environment.yml)
- [../src/maya_cython_compile](../src/maya_cython_compile)
- [../src/maya_tool](../src/maya_tool)
