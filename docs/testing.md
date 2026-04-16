---
summary: "Repo-local lint, type-check, and test commands for documentation and code changes."
read_when:
  - "When validating a docs or code change before handing off."
  - "When updating CI, lint, or type-check instructions."
---

# Testing

For repo changes, prefer the repo-local interpreter path over global `python`.

## Verification commands

```powershell
.\.conda\curvenet-build\python.exe -m ruff check src tests
.\.conda\curvenet-build\python.exe -m mypy src tests
.\.conda\curvenet-build\python.exe -m unittest discover -s tests
```

## What they cover

- `ruff check src tests` - lint and import ordering
- `mypy src tests` - type-checking for the CLI and tests
- `unittest discover -s tests` - CLI, config, and exit-code regression coverage

## Build-path verification

When you are changing pipeline behavior, also validate the command surface you touched:

```powershell
maya-cython-compile doctor
maya-cython-compile run --dry-run
```
