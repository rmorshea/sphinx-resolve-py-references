from __future__ import annotations

import ast
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Any, NamedTuple


class Sentinel:
    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return self.name


def try_resolve_import_value(import_name: str, default: Any) -> Any:
    import_path = import_name.split(".")

    module = None
    for index in range(len(import_path)):
        try:
            module = import_module(".".join(import_path[: index + 1]))
        except ImportError:
            break

    if module is None:
        return default

    value = module
    for attr in import_path[index:]:
        try:
            value = getattr(value, attr)
        except AttributeError:
            return default

    return value


def trace_import_to_source(module: ModuleType, target: str) -> ModuleTarget | None:
    last_module_target: ModuleTarget | None = None
    next_module_target: ModuleTarget | None = ModuleTarget(module, target)

    while next_module_target:
        last_module_target = next_module_target
        next_module_target = _find_next_import_target(*last_module_target)

    return last_module_target


def _find_next_import_target(module: ModuleType, target: str) -> ModuleTarget | None:
    if module.__file__ is None:
        return None

    is_package = Path(module.__file__).name == "__init__.py"

    with open(module.__file__) as f:
        module_ast = ast.parse(f.read())

    for node in ast.walk(module_ast):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            for alias in node.names:
                if alias.asname == target if alias.asname else alias.name == target:
                    if node.level == 0:
                        next_module_name = node.module
                    else:
                        relative_level = node.level - (1 if is_package else 0)
                        relative_slice = slice(0, -relative_level or None)
                        next_module_name = ".".join(
                            module.__name__.split(".")[relative_slice] + [node.module]
                        )
                    return ModuleTarget(import_module(next_module_name), alias.name)
    return None


class ModuleTarget(NamedTuple):
    module: ModuleType
    target: str
