import ast
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Optional, Tuple


def trace_import_to_source(
    module: ModuleType, target: str
) -> Tuple[Optional[ModuleType], Optional[str]]:
    last_module: Optional[ModuleType] = None
    next_module: Optional[ModuleType] = module
    last_target: Optional[str] = None
    next_target: Optional[str] = target

    while True:
        if next_module is None or next_target is None:
            break
        last_module, last_target = next_module, next_target
        next_module, next_target = _find_next_import_target(last_module, next_target)

    return last_module, last_target


def _find_next_import_target(
    module: ModuleType, target: str
) -> Tuple[Optional[ModuleType], Optional[str]]:
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
                    return import_module(next_module_name), alias.name
    return (None, None)
