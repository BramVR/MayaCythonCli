from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

TMP_ROOT = Path(__file__).resolve().parents[1] / "build" / "test-tmp"


def make_temp_repo(name: str) -> Path:
    repo_root = TMP_ROOT / name
    if repo_root.exists():
        shutil.rmtree(repo_root)
    repo_root.mkdir(parents=True, exist_ok=True)
    return repo_root


def write_fake_maya_probe_layout(repo_root: Path, *, library_filename: str) -> tuple[Path, Path, Path]:
    runtime_root = repo_root / "fake-maya"
    mayapy_name = "mayapy.exe" if library_filename.endswith(".lib") else "mayapy"
    mayapy = runtime_root / "bin" / mayapy_name
    mayapy.parent.mkdir(parents=True, exist_ok=True)
    mayapy.write_text("", encoding="utf-8")
    include_dir = runtime_root / "include"
    include_dir.mkdir(parents=True, exist_ok=True)
    library_dir = runtime_root / "lib"
    library_dir.mkdir(parents=True, exist_ok=True)
    library_file = library_dir / library_filename
    library_file.write_text("", encoding="utf-8")
    return mayapy, include_dir, library_file


def make_probe_completed_process(
    *,
    mayapy: Path,
    include_dir: Path,
    library_file: Path,
    runtime_platform: str,
) -> subprocess.CompletedProcess[str]:
    payload = {
        "maya_py": str(mayapy),
        "runtime_platform": runtime_platform,
        "sys_platform": {"windows": "win32", "linux": "linux", "macos": "darwin"}[runtime_platform],
        "sysconfig_platform": runtime_platform,
        "python_version": "3.11.9",
        "python_prefix": str(mayapy.parent.parent),
        "python_base_prefix": str(mayapy.parent.parent),
        "include_dir": str(include_dir),
        "platinclude_dir": str(include_dir),
        "config_vars": {
            "INCLUDEPY": str(include_dir),
            "CONFINCLUDEPY": str(include_dir),
            "LIBDIR": str(library_file.parent),
            "LIBPL": str(library_file.parent),
            "LIBRARY": library_file.name,
            "LDLIBRARY": library_file.name,
            "INSTSONAME": library_file.name,
            "EXT_SUFFIX": ".pyd" if runtime_platform == "windows" else ".so",
            "SOABI": "cpython-311",
        },
    }
    return subprocess.CompletedProcess(
        args=[str(mayapy), "-c", "probe"],
        returncode=0,
        stdout=json.dumps(payload),
        stderr="",
    )
