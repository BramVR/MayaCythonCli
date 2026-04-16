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

Verification:

```powershell
.\.conda\curvenet-build\python.exe -m ruff check src tests
.\.conda\curvenet-build\python.exe -m mypy src tests
.\.conda\curvenet-build\python.exe -m unittest discover -s tests
```

Core files:

- [build-config.json](build-config.json)
- [environment.yml](environment.yml)
- [src/maya_cython_compile](src/maya_cython_compile)
- [src/maya_tool](src/maya_tool)
- [scripts](scripts)
