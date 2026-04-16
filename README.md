# maya-cython-compile

Windows-first CLI for building Maya Python tools into Maya-compatible Cython extension packages.

Docs live in [`docs/`](docs/). Start with:

- [docs/index.md](docs/index.md)
- [docs/quickstart.md](docs/quickstart.md)
- [docs/cli.md](docs/cli.md)
- [docs/config.md](docs/config.md)
- [docs/architecture.md](docs/architecture.md)

Short version:

```powershell
pip install -e .
maya-cython-compile doctor
maya-cython-compile create-env --dry-run
maya-cython-compile create-env --force
maya-cython-compile build --dry-run
maya-cython-compile build --force
maya-cython-compile smoke --force
maya-cython-compile assemble --force
maya-cython-compile run --ensure-env --force
```

Verification, from the repo build env created by `maya-cython-compile create-env`:

```powershell
python -m ruff check src tests
python -m mypy src tests
python -m unittest discover -s tests
```

If the env is not activated, run the same commands with the `python.exe` under your configured `env_path`.

Core files:

- [build-config.json](build-config.json)
- [environment.yml](environment.yml)
- [src/maya_cython_compile](src/maya_cython_compile)
- [src/maya_tool](src/maya_tool)
- [scripts](scripts)
