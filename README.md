# maya-cython-compile

CLI for building Maya Python tools into Maya-compatible Cython extension packages, with explicit named target selection for Maya version, platform, and build-Python combinations.

Docs live in [`docs/`](docs/). Start with:

- [docs/index.md](docs/index.md)
- [docs/quickstart.md](docs/quickstart.md)
- [docs/cli.md](docs/cli.md)
- [docs/config.md](docs/config.md)
- [docs/architecture.md](docs/architecture.md)

Short version:

```powershell
pip install -e .
maya-cython-compile config show --json
maya-cython-compile --target windows-2025 doctor
maya-cython-compile --target windows-2025 create-env --dry-run
maya-cython-compile --target windows-2025 create-env --force
maya-cython-compile --target windows-2025 build --dry-run
maya-cython-compile --target windows-2025 build --force
maya-cython-compile --target windows-2025 smoke --force
maya-cython-compile --target windows-2025 assemble --force
maya-cython-compile --target windows-2025 run --dry-run --ensure-env
maya-cython-compile --target windows-2025 run --ensure-env --force
maya-cython-compile --target windows-2025 verify --list-scenarios
maya-cython-compile --target windows-2025 verify --scenario target-run --json --json-errors
```

On Windows, the PowerShell wrappers under [`scripts/`](scripts/) stay thin delegates over the same target-based CLI. Use `.\scripts\run-pipeline.ps1 -Target windows-2025 -EnsureEnv -Force` when you want the full wrapper-driven flow without baking Maya version or platform defaults into the wrapper layer.

Verification, from the selected target env created by `maya-cython-compile create-env`:

```powershell
python -m ruff check src tests
python -m mypy src tests
python -m unittest discover -s tests
```

Agent-facing verification:

```powershell
maya-cython-compile --target windows-2025 verify --scenario target-dry-run --json
maya-cython-compile --target windows-2025 verify --scenario target-run --json --json-errors
maya-cython-compile --target windows-2025 verify --scenario installed-cli-config-show --json
```

Each verify run writes a repro bundle under `build/agent-runs/` with `summary.json`, per-step logs, copied inputs, and a filesystem snapshot an agent can inspect before patching and rerunning.

If the env is not activated, run the same commands with the `python.exe` under your resolved target `env_path`.

Core files:

- [build-config.json](build-config.json)
- [environment.yml](environment.yml)
- [src/maya_cython_compile](src/maya_cython_compile)
- [src/maya_tool](src/maya_tool)
- [scripts](scripts)
