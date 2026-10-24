"""Static import scanning for the layer tests (INV-07 for engine/, ADR-005 for render/)."""

import ast


def imported_modules(source: str, package: str) -> list[tuple[int, str]]:
    """(line, absolute module name) for every import in `source`, nothing executed.

    `package` is the dotted package the file lives in ("engine" for engine/step.py), needed to resolve
    relative imports such as `from ..tools import x`.
    """
    imported: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported += [(node.lineno, alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = package.split(".")[: len(package.split(".")) - (node.level - 1)] if node.level else []
            if node.module:
                imported.append((node.lineno, ".".join(base + [node.module])))
            else:  # `from . import rng` / `from .. import logs`: each name is a module
                imported += [(node.lineno, ".".join(base + [alias.name])) for alias in node.names]
    return imported
