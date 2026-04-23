from __future__ import annotations

import ast
import json
import shutil
from pathlib import Path

from .config import ResolvedConfig, SourceMapping

ARTIFACT_METADATA_FILENAME = "maya_cython_compile_artifact.json"


def prepare_build_tree(config: ResolvedConfig) -> Path:
    build_root = config.repo_root / "build" / "target-build" / config.build.target_name

    package_target = build_root / config.build.package_dir
    package_target.mkdir(parents=True, exist_ok=True)
    stage_package_sources(config, build_root, package_target)
    ensure_package_init(package_target)
    rewrite_package_sources(config, package_target)

    (build_root / "build-config.json").write_text(
        json.dumps(
            {
                "target_name": config.build.target_name,
                "platform": config.build.platform,
                "distribution_name": config.build.distribution_name,
                "package_name": config.build.package_name,
                "package_dir": config.build.package_dir,
                "version": config.build.version,
                "compiled_modules": config.build.compiled_modules,
                "package_data": config.build.package_data,
                "artifact_metadata": render_artifact_metadata(config),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (build_root / "setup.py").write_text(render_setup_py(), encoding="utf-8")
    (build_root / "pyproject.toml").write_text(render_pyproject_toml(), encoding="utf-8")
    return build_root


def render_artifact_metadata(config: ResolvedConfig) -> dict[str, str | int]:
    return {
        "schema_version": 1,
        "target_name": config.build.target_name,
        "platform": config.build.platform,
        "maya_version": config.build.maya_version,
        "python_version": config.build.python_version,
        "distribution_name": config.build.distribution_name,
        "package_name": config.build.package_name,
        "module_name": config.build.module_name,
        "version": config.build.version,
    }


def render_pyproject_toml() -> str:
    return """[build-system]
requires = [
    "setuptools>=69",
    "wheel",
    "Cython>=3.0",
]
build-backend = "setuptools.build_meta"
"""


def render_setup_py() -> str:
    return """import json
import os
from pathlib import Path

from setuptools import Extension, find_packages, setup
from setuptools.command.bdist_wheel import bdist_wheel as _bdist_wheel
from setuptools.command.build_py import build_py as _build_py

try:
    from Cython.Build import cythonize
except ImportError as exc:
    raise RuntimeError("Cython is required to build this project.") from exc


ROOT = Path(__file__).resolve().parent
with (ROOT / "build-config.json").open("r", encoding="utf-8") as f:
    CONFIG = json.load(f)

PACKAGE_NAME = CONFIG["package_name"]
PACKAGE_DIR = Path(CONFIG["package_dir"])
DIST_NAME = CONFIG["distribution_name"]
VERSION = CONFIG["version"]
COMPILED_MODULES = tuple(CONFIG["compiled_modules"])
PACKAGE_DATA = list(CONFIG.get("package_data", []))
PACKAGE_PARENT = Path(CONFIG["package_dir"]).parent
ARTIFACT_METADATA = dict(CONFIG["artifact_metadata"])
MAYA_PYTHON_INCLUDE = os.environ.get("MAYA_PYTHON_INCLUDE")
MAYA_PYTHON_LIBDIR = os.environ.get("MAYA_PYTHON_LIBDIR")
MAYA_PYTHON_LIBNAME = os.environ.get("MAYA_PYTHON_LIBNAME", "python311")
ARTIFACT_METADATA_FILE = "maya_cython_compile_artifact.json"

if not MAYA_PYTHON_INCLUDE or not MAYA_PYTHON_LIBDIR:
    raise RuntimeError("Set MAYA_PYTHON_INCLUDE and MAYA_PYTHON_LIBDIR before building.")


def ext_source(module_name: str) -> str:
    return str(PACKAGE_DIR / f"{module_name.replace('.', '/')}.py")


def module_py_path(module_name: str) -> Path:
    parts = module_name.split(".")
    return Path(*parts[:-1], f"{parts[-1]}.py")


def package_discovery_root() -> str:
    parent = PACKAGE_PARENT.as_posix()
    return parent if parent and parent != "." else "."


class build_py(_build_py):
    def run(self):
        super().run()
        package_build_dir = Path(self.build_lib) / PACKAGE_NAME
        for module_name in COMPILED_MODULES:
            target = package_build_dir / module_py_path(module_name)
            if target.exists():
                target.unlink()


class bdist_wheel(_bdist_wheel):
    def write_wheelfile(self, wheelfile_base, generator=None):
        metadata_path = Path(wheelfile_base) / ARTIFACT_METADATA_FILE
        metadata_path.write_text(
            json.dumps(ARTIFACT_METADATA, indent=2) + "\\n",
            encoding="utf-8",
        )
        super().write_wheelfile(wheelfile_base, generator=generator)


extensions = [
    Extension(
        name=f"{PACKAGE_NAME}.{module_name}",
        sources=[ext_source(module_name)],
        include_dirs=[MAYA_PYTHON_INCLUDE],
        library_dirs=[MAYA_PYTHON_LIBDIR],
        libraries=[MAYA_PYTHON_LIBNAME],
    )
    for module_name in COMPILED_MODULES
]

setup(
    name=DIST_NAME,
    version=VERSION,
    description="Generic Maya+Cython build scaffold",
    packages=[
        package_name
        for package_name in find_packages(where=package_discovery_root())
        if package_name == PACKAGE_NAME or package_name.startswith(f"{PACKAGE_NAME}.")
    ],
    package_dir={"": package_discovery_root()},
    package_data={PACKAGE_NAME: PACKAGE_DATA},
    include_package_data=True,
    zip_safe=False,
    cmdclass={"build_py": build_py, "bdist_wheel": bdist_wheel},
    ext_modules=cythonize(
        extensions,
        compiler_directives={"language_level": "3"},
        build_dir="build/cython",
    ),
)
"""


def stage_package_sources(config: ResolvedConfig, build_root: Path, package_target: Path) -> None:
    mappings = config.build.build_tree.source_mappings
    if not mappings:
        package_source = config.repo_root / config.build.package_dir
        copy_source_path(package_source, package_target)
        return

    for mapping in mappings:
        apply_source_mapping(config.repo_root, build_root, mapping)


def apply_source_mapping(repo_root: Path, build_root: Path, mapping: SourceMapping) -> None:
    source = (repo_root / mapping.source).resolve()
    destination = build_root / mapping.destination
    if not source.exists():
        raise FileNotFoundError(f"Configured build_tree source path does not exist: {source}")

    if source.is_dir() and mapping.expand_children:
        destination.mkdir(parents=True, exist_ok=True)
        for child in sorted(source.iterdir(), key=lambda item: item.name):
            copy_source_path(child, destination / child.name)
        return

    copy_source_path(source, destination)


def copy_source_path(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def ensure_package_init(package_target: Path) -> None:
    init_file = package_target / "__init__.py"
    if not init_file.exists():
        init_file.write_text("", encoding="utf-8")


def rewrite_package_sources(config: ResolvedConfig, package_target: Path) -> None:
    if not config.build.build_tree.rewrite_local_imports and not config.build.build_tree.import_rewrites:
        return

    local_modules = discover_local_modules(package_target)
    for path in sorted(package_target.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        rewritten = rewrite_python_imports(
            source,
            current_path=path,
            package_target=package_target,
            local_modules=local_modules,
            rewrite_local_imports=config.build.build_tree.rewrite_local_imports,
            import_rewrites=config.build.build_tree.import_rewrites,
        )
        if rewritten != source:
            path.write_text(rewritten, encoding="utf-8")


def discover_local_modules(package_target: Path) -> set[str]:
    local_modules: set[str] = set()
    for child in package_target.iterdir():
        if child.is_file() and child.suffix == ".py" and child.name != "__init__.py":
            local_modules.add(child.stem)
        if child.is_dir() and (child / "__init__.py").exists():
            local_modules.add(child.name)
    return local_modules


def rewrite_python_imports(
    source: str,
    *,
    current_path: Path,
    package_target: Path,
    local_modules: set[str],
    rewrite_local_imports: bool,
    import_rewrites: dict[str, str],
) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    current_top_level = current_module_root(current_path, package_target)
    transformer = PackageImportTransformer(
        current_top_level=current_top_level,
        local_modules=local_modules,
        rewrite_local_imports=rewrite_local_imports,
        import_rewrites=import_rewrites,
    )
    rewritten_tree = transformer.visit(tree)
    ast.fix_missing_locations(rewritten_tree)
    rendered = ast.unparse(rewritten_tree)
    if source.endswith("\n"):
        rendered += "\n"
    return rendered


def current_module_root(current_path: Path, package_target: Path) -> str | None:
    relative = current_path.relative_to(package_target)
    return relative.parts[0] if relative.parts else None


class PackageImportTransformer(ast.NodeTransformer):
    def __init__(
        self,
        *,
        current_top_level: str | None,
        local_modules: set[str],
        rewrite_local_imports: bool,
        import_rewrites: dict[str, str],
    ) -> None:
        self.current_top_level = current_top_level
        self.local_modules = local_modules
        self.rewrite_local_imports = rewrite_local_imports
        self.import_rewrites = import_rewrites

    def visit_Import(self, node: ast.Import) -> ast.stmt | list[ast.stmt]:
        statements: list[ast.stmt] = []
        regular_aliases: list[ast.alias] = []
        for alias in node.names:
            rewritten = self.rewrite_import_alias(alias)
            if rewritten is None:
                regular_aliases.append(alias)
                continue
            if regular_aliases:
                statements.append(ast.Import(names=regular_aliases))
                regular_aliases = []
            if isinstance(rewritten, list):
                statements.extend(rewritten)
            else:
                statements.append(rewritten)
        if regular_aliases:
            statements.append(ast.Import(names=regular_aliases))
        if not statements:
            return node
        if len(statements) == 1:
            return statements[0]
        return statements

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.stmt:
        if node.level != 0 or node.module is None:
            return node

        replacement = self.rewrite_module_path(node.module)
        if replacement is None:
            return node
        module = ".".join(replacement) if replacement else None
        return ast.ImportFrom(module=module, names=node.names, level=1)

    def rewrite_import_alias(self, alias: ast.alias) -> ast.stmt | list[ast.stmt] | None:
        replacement = self.rewrite_module_path(alias.name)
        if replacement is None:
            return None
        if not replacement:
            return None

        if alias.asname is None and len(replacement) > 1:
            return self.rewrite_import_chain(replacement)
        if len(replacement) == 1:
            return ast.ImportFrom(module=None, names=[ast.alias(name=replacement[0], asname=alias.asname)], level=1)
        return ast.ImportFrom(
            module=".".join(replacement[:-1]),
            names=[ast.alias(name=replacement[-1], asname=alias.asname)],
            level=1,
        )

    def rewrite_import_chain(self, replacement: list[str]) -> list[ast.stmt]:
        statements: list[ast.stmt] = [
            ast.ImportFrom(module=None, names=[ast.alias(name=replacement[0], asname=None)], level=1)
        ]
        for index in range(1, len(replacement)):
            statements.append(
                ast.ImportFrom(
                    module=".".join(replacement[:index]),
                    names=[ast.alias(name=replacement[index], asname=None)],
                    level=1,
                )
            )
        return statements

    def rewrite_module_path(self, module_name: str) -> list[str] | None:
        parts = module_name.split(".")
        rewritten_local = self.rewrite_local_module(parts)
        if rewritten_local is not None:
            return rewritten_local
        return self.rewrite_explicit_mapping(parts)

    def rewrite_local_module(self, parts: list[str]) -> list[str] | None:
        if not self.rewrite_local_imports or not parts:
            return None
        if parts[0] == self.current_top_level:
            return None
        if parts[0] not in self.local_modules:
            return None
        return parts

    def rewrite_explicit_mapping(self, parts: list[str]) -> list[str] | None:
        best_match: tuple[str, str] | None = None
        dotted = ".".join(parts)
        for raw_prefix, replacement in self.import_rewrites.items():
            if dotted == raw_prefix or dotted.startswith(f"{raw_prefix}."):
                if best_match is None or len(raw_prefix) > len(best_match[0]):
                    best_match = (raw_prefix, replacement)
        if best_match is None:
            return None

        raw_prefix, replacement = best_match
        prefix_parts = raw_prefix.split(".")
        remainder = parts[len(prefix_parts) :]
        replacement_parts = [part for part in replacement.strip(".").split(".") if part]
        return replacement_parts + remainder
