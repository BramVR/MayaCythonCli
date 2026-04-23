---
summary: "Repo-local lint, type-check, and test commands for documentation and code changes."
read_when:
  - "When validating a docs or code change before handing off."
  - "When updating CI, lint, or type-check instructions."
---

# Testing

For repo changes, prefer the selected target build env over a global interpreter. Activate the env created by `maya-cython-compile create-env`, then run:

## Verification commands

```powershell
python -m ruff check src tests
python -m mypy src tests
python -m unittest discover -s tests
```

If the env is not activated, run the same commands with the `python.exe` under your resolved target `env_path`.

GitHub Actions runs the same lint, type-check, and unittest commands on `windows-latest`, then promotes to:

```powershell
python -m maya_cython_compile --repo-root . --target windows-2025 verify --scenario installed-cli-config-show --json --json-errors
```

That CI path stays cheap because it does not require Maya or a self-hosted runner, but it still exercises wheel packaging plus the installed CLI entrypoint.

## What they cover

- `ruff check src tests` - lint and import ordering
- `mypy src tests` - type-checking for the CLI and tests
- `unittest discover -s tests` - CLI, pipeline, wrapper-forwarding, config, and exit-code regression coverage

## Build-path verification

When you are changing pipeline behavior, also validate the command surface you touched for a representative target:

```powershell
maya-cython-compile --target windows-2025 config show
maya-cython-compile --target windows-2025 doctor
maya-cython-compile --target windows-2025 run --dry-run --ensure-env
```

## Agent-facing verification

Use `verify` when you want one command an agent can rerun, inspect, and promote after a patch.

```powershell
maya-cython-compile --target windows-2025 verify --list-scenarios
maya-cython-compile --target windows-2025 verify --scenario target-dry-run --json
maya-cython-compile --target windows-2025 verify --scenario target-run --json --json-errors
maya-cython-compile --target windows-2025 verify --scenario installed-cli-config-show --json
```

The default run bundle root is `build/agent-runs/`. Each run writes:

- `summary.json` with `scenario`, `stage`, `exit_code`, `commands`, and target artifact paths
- `steps/*.stdout.log` and `steps/*.stderr.log`
- `inputs/` snapshots for `build-config.json`, `environment.yml`, and local config when present
- `filesystem.txt` with the current target output tree snapshot

Recommended loop:

1. When the repo, machine config, or Maya toolchain state is still uncertain, start with `verify --scenario target-dry-run --json`.
2. Confirm that `doctor` resolves the right target and that the previewed `create-env`, `build`, `smoke`, and `assemble` commands point at the expected repo paths.
3. Promote to `verify --scenario target-run --json --json-errors`.
4. If it fails, inspect `summary.json` and the failed step log.
5. Patch the repo.
6. Rerun the same verify scenario until it passes.
7. Promote to `ruff`, `mypy`, and `unittest discover`.

Notes:

- `target-dry-run` does not prove that `<repo-root>/environment.yml` exists, because it only previews the `create-env` command.
- `target-run` does require `<repo-root>/environment.yml` once it reaches `create-env`.
- A successful smoke run can still contain non-fatal Maya warnings in `smoke_output`. Use the verify step exit code plus the smoke logs together when triaging.
