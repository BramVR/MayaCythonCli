from pathlib import Path


def resource_path(name: str) -> str:
    return str(Path(__file__).resolve().with_name(name))
