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

## What they cover

- `ruff check src tests` - lint and import ordering
- `mypy src tests` - type-checking for the CLI and tests
- `unittest discover -s tests` - CLI, config, and exit-code regression coverage

## Build-path verification

When you are changing pipeline behavior, also validate the command surface you touched for a representative target:

```powershell
maya-cython-compile --target windows-2025 config show
maya-cython-compile --target windows-2025 doctor
maya-cython-compile --target windows-2025 run --dry-run
```
