from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
import zipfile
from pathlib import Path
from typing import Any

from .config import ResolvedConfig, as_dict
from .errors import BUILD_ERROR, CliError, DEPENDENCY_ERROR, SMOKE_ERROR
from .target_builder import prepare_build_tree


def show_config(config: ResolvedConfig) -> dict[str, Any]:
    return as_dict(config)


def doctor(config: ResolvedConfig) -> dict[str, Any]:
    maya = probe_maya_runtime(config.local.maya_py)
    return {
        "config": show_config(config),
        "checks": {
            "conda_exe_exists": config.local.conda_exe.exists(),
            "env_exists": config.local.env_path.exists(),
            "maya_py_exists": config.local.maya_py.exists(),
            "maya_include_exists": maya["include_dir"] is not None,
            "maya_lib_exists": maya["lib_dir"] is not None and maya["lib_name"] is not None,
        },
        "maya_runtime": maya,
    }


def create_env(config: ResolvedConfig, *, verbose: bool = False) -> dict[str, Any]:
    if not config.local.conda_exe.exists():
        raise CliError(f"Conda was not found at {config.local.conda_exe}", DEPENDENCY_ERROR)

    command = [
        "cmd.exe",
        "/c",
        str(config.local.conda_exe),
        "env",
        "create",
        "--prefix",
        str(config.local.env_path),
        "--force",
        "--file",
        str(config.repo_root / "environment.yml"),
    ]
    run_command(command, cwd=config.repo_root, verbose=verbose, error_code=DEPENDENCY_ERROR)
    return {"env_path": str(config.local.env_path)}


def build(config: ResolvedConfig, *, verbose: bool = False) -> dict[str, Any]:
    if not config.local.env_path.exists():
        raise CliError(
            f"Conda environment missing: {config.local.env_path}. Run create-env first.",
            DEPENDENCY_ERROR,
        )

    maya = probe_maya_runtime(config.local.maya_py)
    if not maya["include_dir"] or not maya["lib_dir"] or not maya["lib_name"]:
        raise CliError(f"Could not resolve Maya Python runtime from {config.local.maya_py}", DEPENDENCY_ERROR)

    clean_build_artifacts(config.repo_root)
    build_tree = prepare_build_tree(config)
    dist_dir = config.repo_root / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    temp_root = config.repo_root / "build" / "tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["MAYA_PYTHON_INCLUDE"] = str(maya["include_dir"])
    env["MAYA_PYTHON_LIBDIR"] = str(maya["lib_dir"])
    env["MAYA_PYTHON_LIBNAME"] = str(maya["lib_name"])
    env["TEMP"] = str(temp_root)
    env["TMP"] = str(temp_root)

    command = [
        "cmd.exe",
        "/c",
        str(config.local.conda_exe),
        "run",
        "--prefix",
        str(config.local.env_path),
        "python",
        "setup.py",
        "bdist_wheel",
        "--dist-dir",
        str(dist_dir),
    ]
    run_command(command, cwd=build_tree, env=env, verbose=verbose, error_code=BUILD_ERROR)
    wheel = latest_wheel(config)
    return {"wheel": str(wheel)}


def smoke(config: ResolvedConfig, *, verbose: bool = False) -> dict[str, Any]:
    wheel = latest_wheel(config)
    if not config.local.maya_py.exists():
        raise CliError(f"mayapy not found: {config.local.maya_py}", DEPENDENCY_ERROR)

    smoke_root = config.repo_root / "build" / "smoke"
    extract_dir = smoke_root / "wheel"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(extract_dir)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(extract_dir)
    command = [str(config.local.maya_py), "-c", smoke_script(config)]
    result = run_command(command, cwd=config.repo_root, env=env, verbose=verbose, error_code=SMOKE_ERROR)
    output = result.stdout.strip()
    return {"wheel": str(wheel), "smoke_output": output.splitlines()}


def assemble(
    config: ResolvedConfig,
    *,
    module_name: str | None = None,
    maya_version: str | None = None,
) -> dict[str, Any]:
    wheel = latest_wheel(config)
    resolved_module = module_name or config.build.module_name
    resolved_maya_version = maya_version or config.build.maya_version
    module_root = config.repo_root / "dist" / "module" / resolved_module
    scripts_root = module_root / "contents" / "scripts"
    if module_root.exists():
        shutil.rmtree(module_root)
    scripts_root.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(wheel) as archive:
        for member in archive.infolist():
            top = member.filename.split("/", 1)[0]
            if top.endswith(".dist-info") or top.endswith(".data"):
                continue
            archive.extract(member, scripts_root)

    mod_path = module_root / f"{resolved_module}.mod"
    mod_path.write_text(
        f"+ MAYAVERSION:{resolved_maya_version} PLATFORM:win64 {resolved_module} {config.build.version} .\\contents",
        encoding="utf-8",
    )
    return {"module_root": str(module_root), "module_file": str(mod_path)}


def run_pipeline(
    config: ResolvedConfig,
    *,
    verbose: bool = False,
    ensure_env: bool = False,
    skip_smoke: bool = False,
    skip_assemble: bool = False,
    module_name: str | None = None,
    maya_version: str | None = None,
) -> dict[str, Any]:
    steps: dict[str, Any] = {}
    if ensure_env and not config.local.env_path.exists():
        steps["create_env"] = create_env(config, verbose=verbose)
    steps["build"] = build(config, verbose=verbose)
    if not skip_smoke:
        steps["smoke"] = smoke(config, verbose=verbose)
    if not skip_assemble:
        steps["assemble"] = assemble(
            config,
            module_name=module_name,
            maya_version=maya_version,
        )
    return steps


def probe_maya_runtime(maya_py: Path) -> dict[str, str | None]:
    if not maya_py.exists():
        return {"maya_py": str(maya_py), "include_dir": None, "lib_dir": None, "lib_name": None}

    maya_root = maya_py.parent.parent
    include_dir = maya_root / "Python" / "Include"
    if not include_dir.exists():
        headers = sorted(maya_root.rglob("Python.h"))
        include_dir = headers[0].parent if headers else None

    lib_dir = maya_root / "lib"
    lib_name = None
    if lib_dir.exists():
        libs = sorted(lib_dir.glob("python*.lib"))
        if libs:
            lib_name = libs[0].stem
    else:
        lib_dir = None

    return {
        "maya_py": str(maya_py),
        "include_dir": str(include_dir) if include_dir else None,
        "lib_dir": str(lib_dir) if lib_dir else None,
        "lib_name": lib_name,
    }


def clean_build_artifacts(repo_root: Path) -> None:
    build_root = repo_root / "build"
    if build_root.exists():
        for pattern in ("lib.*", "bdist.*", "temp.*", "cython", "target-build", "tmp"):
            for path in build_root.glob(pattern):
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
    for egg_info in repo_root.glob("*.egg-info"):
        if egg_info.is_dir():
            shutil.rmtree(egg_info)


def latest_wheel(config: ResolvedConfig) -> Path:
    dist_dir = config.repo_root / "dist"
    distribution = config.build.distribution_name.replace("-", "_")
    wheels = sorted(
        dist_dir.glob(f"{distribution}-*.whl"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if not wheels:
        raise CliError(f"No built wheel found in {dist_dir}", BUILD_ERROR)
    return wheels[0]


def smoke_script(config: ResolvedConfig) -> str:
    imports = "\n".join(
        f"importlib.import_module('{config.build.package_name}.{module_name}')"
        for module_name in config.build.smoke.compiled_modules
    )
    callable_block = ""
    if config.build.smoke.callable:
        callable_block = textwrap.dedent(
            f"""
            package = importlib.import_module('{config.build.package_name}')
            print(getattr(package, '{config.build.smoke.callable}')())
            """
        )
    resource_block = ""
    if config.build.smoke.resource_check:
        resource_block = textwrap.dedent(
            f"""
            package_files = resources.files('{config.build.package_name}')
            print(package_files.joinpath('{config.build.smoke.resource_check}').is_file())
            """
        )
    return textwrap.dedent(
        f"""
        import importlib
        from importlib import resources

        importlib.import_module('{config.build.package_name}')
        {imports}
        {callable_block}
        {resource_block}
        """
    ).strip()


def run_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    verbose: bool = False,
    error_code: int,
) -> subprocess.CompletedProcess[str]:
    if verbose:
        print(f"$ {' '.join(command)}", file=sys.stderr)

    result = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Command failed."
        raise CliError(message, error_code)
    return result
