# Vision

MayaCythonCli is a target-based CLI for compiling Maya Python tools into Maya-compatible Cython extension packages. It should keep the build pipeline explicit, scriptable, reproducible, and friendly to agents working across Maya, Windows, and package assembly boundaries.

## Merge by Default

- Bug fixes in target resolution, config loading, wrappers, build staging, smoke, verify, or packaging.
- Small CLI improvements that preserve stable JSON/text output and documented exit behavior.
- Documentation updates for commands, config, wrappers, architecture, and verification.
- Tests and repro-bundle improvements that make agent debugging easier.
- Pipeline fixes that keep PowerShell wrappers thin delegates over the same CLI.

## Needs Sign-Off

- New build systems, package managers, or runtime language changes.
- Broad changes to build-tree layout, source mapping semantics, or target config shape.
- Maya-version/platform support that cannot be verified on a suitable target.
- Changes that hide build steps, make destructive filesystem edits, or weaken repro bundles.
- Auto-install or environment mutation behavior beyond the documented explicit commands.
