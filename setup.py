import os
import json
from pathlib import Path

from setuptools import Extension, setup
from setuptools.command.build_py import build_py as _build_py

try:
    from Cython.Build import cythonize
except ImportError as exc:
    raise RuntimeError("Cython is required to build this project.") from exc


ROOT = Path(__file__).resolve().parent
with (ROOT / "build-config.json").open("r", encoding="utf-8") as f:
    CONFIG = json.load(f)

PACKAGE_NAME = CONFIG["package_name"]
PACKAGE_DIR = ROOT / CONFIG["package_dir"]
DIST_NAME = CONFIG["distribution_name"]
VERSION = CONFIG["version"]
COMPILED_MODULES = tuple(CONFIG["compiled_modules"])
PACKAGE_DATA = CONFIG.get("package_data", [])
MAYA_PYTHON_INCLUDE = os.environ.get("MAYA_PYTHON_INCLUDE")
MAYA_PYTHON_LIBDIR = os.environ.get("MAYA_PYTHON_LIBDIR")
MAYA_PYTHON_LIBNAME = os.environ.get("MAYA_PYTHON_LIBNAME", "python311")

if not MAYA_PYTHON_INCLUDE or not MAYA_PYTHON_LIBDIR:
    raise RuntimeError(
        "Set MAYA_PYTHON_INCLUDE and MAYA_PYTHON_LIBDIR before building."
    )


def ext_source(module_name: str) -> str:
    return str(PACKAGE_DIR / f"{module_name.replace('.', '/')}.py")


def module_py_path(module_name: str) -> Path:
    parts = module_name.split(".")
    return Path(*parts[:-1], f"{parts[-1]}.py")


class build_py(_build_py):
    def run(self):
        super().run()
        package_build_dir = Path(self.build_lib) / PACKAGE_NAME
        for module_name in COMPILED_MODULES:
            target = package_build_dir / module_py_path(module_name)
            if target.exists():
                target.unlink()


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
    packages=[PACKAGE_NAME],
    package_dir={PACKAGE_NAME: CONFIG["package_dir"]},
    package_data={PACKAGE_NAME: PACKAGE_DATA},
    include_package_data=True,
    zip_safe=False,
    cmdclass={"build_py": build_py},
    ext_modules=cythonize(
        extensions,
        compiler_directives={"language_level": "3"},
        build_dir=str(ROOT / "build" / "cython"),
    ),
)
