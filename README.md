# maya-cython-compile

Windows-first CLI for building Maya Python tools into Maya-compatible Cython extension packages.

The repo is now documented from `/docs` instead of keeping the full manual in the root README.

Start with:

- [docs/README.md](docs/README.md)
- [docs/pipeline-quickstart.md](docs/pipeline-quickstart.md)
- [docs/cli-reference.md](docs/cli-reference.md)
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

Quality checks:

```powershell
python -m ruff check src tests
python -m mypy src tests
python -m unittest discover -s tests
```

Core files:

- [build-config.json](build-config.json)
- [environment.yml](environment.yml)
- [src/maya_cython_compile](src/maya_cython_compile)
- [src/maya_tool](src/maya_tool)
- [scripts](scripts)
