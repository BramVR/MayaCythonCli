## Workflow

Use this reference when the skill has already triggered and you need the shortest safe command path.

### Golden path

1. Show resolved config:

   ```powershell
   maya-cython-compile config show --json
   ```

2. Determine the target from repo config or the active task, then confirm it is sane:

   ```powershell
   maya-cython-compile --target <target> doctor
   ```

3. Validate setup and plan without executing destructive steps:

   ```powershell
   maya-cython-compile --target <target> verify --scenario target-dry-run --json
   ```

4. Run the full target loop only after the dry-run result is understood:

   ```powershell
   maya-cython-compile --target <target> verify --scenario target-run --json --json-errors
   ```

### Packaging and entrypoint checks

When changing packaging metadata, console scripts, or installed CLI behavior:

```powershell
maya-cython-compile --target <target> verify --scenario installed-cli-config-show --json
```

### Repair loop

When a verify scenario fails:

1. Open the newest `build/agent-runs/<run>/summary.json`.
2. Read the per-step logs from the same bundle.
3. Patch the root cause, not the first visible symptom.
4. Re-run the same scenario before broadening validation.
5. Resolve the target environment path from `config show --json`.
6. If code changed, run the repo checks with that interpreter:

   ```powershell
   <env-python> -m ruff check src tests
   <env-python> -m mypy src tests
   <env-python> -m unittest discover -s tests
   ```

Use `python -m ...` directly only when that resolved environment is already active.
