def normalize_node_name(name: str) -> str:
    if not name:
        return "unknown"
    return name.replace("|", "_").replace(":", "_").lstrip("_")
