"""Python entrypoints should stay here and import compiled internals as needed."""

from . import _cy_logic


def show_ui():
    """Placeholder entrypoint for future Maya UI/bootstrap code."""
    return _cy_logic.normalize_node_name("|placeholder|ns:tool")
