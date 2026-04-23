---
name: maya-cython-compile
description: Use the `maya-cython-compile` CLI when Codex needs to build, verify, debug, or package Maya Python tools into Maya-compatible Cython extension outputs, especially for target-scoped environment setup, dry-run validation, full pipeline verification, or inspection of `build/agent-runs/` repro bundles after a failed run.
---

# Maya Cython Compile

Use the CLI as the source of truth. Prefer its target-aware subcommands and verify scenarios over ad hoc shell chains whenever the CLI can express the same workflow directly. Treat repo docs as optional background, not as a prerequisite for using the skill after it has been installed globally.

## Main use case

Use this skill when an agent needs to:

- inspect resolved build config before changing packaging or pipeline code
- validate whether a Maya/Cython target is wired correctly
- run the safe dry-run planning path before executing destructive or expensive steps
- debug a failed compile pipeline by inspecting `build/agent-runs/`
- verify installed CLI behavior after packaging or entrypoint changes

## Golden path

1. Show the resolved config first:
   - `maya-cython-compile config show --json`
2. Determine the target from repo config or the user task. Do not guess if the active target is unclear.
3. Confirm the chosen target is sane:
   - `maya-cython-compile --target <target> doctor`
4. If environment, Maya, Conda, or wrapper state may be wrong, plan first:
   - `maya-cython-compile --target <target> verify --scenario target-dry-run --json`
5. Run the full loop only after the dry-run result is understood:
   - `maya-cython-compile --target <target> verify --scenario target-run --json --json-errors`

## Scenario choice

- Use `target-dry-run` first when target selection, Conda paths, Maya paths, or wrapper state may be wrong.
- Use `target-run` when you need the full create-env, build, smoke, assemble, and run loop.
- Use `installed-cli-config-show` when touching packaging, entrypoints, or installed CLI resolution.

## Commands

- Show help once per session if the command surface is unfamiliar:
  - `maya-cython-compile --help`
- Show config:
  - `maya-cython-compile config show --json`
- Sanity-check one target:
  - `maya-cython-compile --target <target> doctor`
- Preview the target flow:
  - `maya-cython-compile --target <target> verify --scenario target-dry-run --json`
- Run the full verification loop:
  - `maya-cython-compile --target <target> verify --scenario target-run --json --json-errors`
- Check installed CLI packaging and entrypoints:
  - `maya-cython-compile --target <target> verify --scenario installed-cli-config-show --json`

Read `references/workflow.md` when you need the repair loop or the post-fix verification sequence.

## Failure handling

- Inspect the latest repro bundle under `build/agent-runs/` before patching.
- Re-run the same verify scenario first after a fix so the failure surface stays comparable.
- After the verify scenario passes, run lint, type-check, and tests from the resolved target environment if code changed.
- Prefer direct CLI commands over wrapper scripts unless wrapper behavior itself is under investigation.

## Safety

- Do not assume this skill is running inside the tool's own repo. Use local repo docs only when they exist and are relevant.
- Do not guess target defaults if the repo or user already specifies one; confirm with `config show`.
- Keep fixes inside the repo or target-owned build outputs. Do not hand-edit generated artifacts under `dist/` unless the task is explicitly about assembled output inspection.
- Treat `--dry-run` output as the planning surface and `--force` as the explicit opt-in for destructive or expensive steps.
