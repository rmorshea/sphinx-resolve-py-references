"""Fixes or warns about missing references to Python objects in the docs

The extension is useful because it's often annoying to write out the full path
to an object in your docs which you know is imported in the current module.
This is also true for neighboring modules which would be easier referenced with
a relative name.

This extension resolves these issues by allowing you to reference functions or classes
which are imported in the current module as if they had been defined there and creates
a backlink to their true location.

Examples:

    .. code-block::

        from some_package import MyClass

        def my_function():
            '''Uses :class:`MyClass`'''
            # The above reference would normally fail because `MyClass`
            # is not defined in this module. However this extension
            # automatically resolves the reference

Notes:

    This is done by analyzing the AST to extra ``import`` statements and tracing them
    back to the place where the target was defined. This is more robust than looking at
    the ``__module__`` and ``__name__`` attributes of classes and functions because it
    won't work for any module attributes that have been documented (e.g. global variables).
"""
from __future__ import annotations

import builtins
import distutils.sysconfig as sysconfig
import inspect
import re
import sys
from enum import Enum
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Any

from docutils.nodes import Element, TextElement
from docutils.nodes import reference as Reference
from sphinx.application import Sphinx
from sphinx.domains.python import PythonDomain
from sphinx.environment import BuildEnvironment
from sphinx.ext.intersphinx import missing_reference as intersphinx_get_missing_ref
from sphinx.util import logging

from .utils import Sentinel, trace_import_to_source, try_resolve_import_value


logger = logging.getLogger(__name__)
UNDEFINED = Sentinel("UNDEFINED")
SKIP = Sentinel("SKIP")


class Result(Enum):
    skip = "skip"
    undefined = "undefined"


def resolve_py_reference(
    app: Sphinx, env: BuildEnvironment, node: Element, contnode: TextElement
) -> Reference | None:
    if _skip_node(app, node):
        return None

    result = _resolve_imported_value(app, env, node, contnode)
    assert result is not None, "defensive check"

    if isinstance(result, Sentinel):
        if result is UNDEFINED:
            _log_no_referent_warning(node)
        return None

    return result


SOURCE_DESCRIPTION_PATTERN = re.compile(r"(?P<file>.*):docstring of (?P<import>.*)")


def _log_no_referent_warning(node: Element) -> None:
    if node.source:
        if Path(node.source).is_file():
            src = f"{node.source}:{node.line} via module {node['py:module']}"
        else:
            match = SOURCE_DESCRIPTION_PATTERN.match(node.source)
            if match:
                file = match.group("file")
                import_name = match.group("import")
                value = try_resolve_import_value(import_name, UNDEFINED)
                if value is UNDEFINED:
                    src = node.source
                else:
                    try:
                        lineno = inspect.getsourcelines(value)[1]
                    except OSError:
                        src = node.source
                    else:
                        src = f"{file}:{lineno} (docstring of {import_name})"
            else:
                src = node.source
    else:
        src = node["py:module"]

    try:
        index_in_source: int = node.rawsource.index(node["reftarget"])
    except ValueError:
        # raw source does not contain reftarget in case of type hint alias
        is_relative = False
    else:
        is_relative = node.rawsource[index_in_source - 1 : index_in_source] == "."

    reftarget = ("." if is_relative else "") + node["reftarget"]
    logger.warning(f"No referent for name {reftarget!r} at {src}")


def _skip_node(app: Sphinx, node: Element) -> bool:
    return (
        "refdoc" not in node
        or node["refdomain"] != "py"
        or "py:module" not in node
        or node["py:module"] is None
        or any(
            re.match(pattern, node["reftarget"])
            for pattern in app.config.allowed_missing_py_references
        )
        or node["reftarget"].split(".", 1)[0] in _STD_LIB_MODULES
        or hasattr(builtins, node["reftarget"])
        or _is_ref_to_external_package(node)
    )


_STD_LIB_MODULES = list(sys.builtin_module_names)
for path in Path(sysconfig.get_python_lib(standard_lib=True)).iterdir():
    if (
        path.is_file()
        and path.suffixes == [".py"]
        or path.is_dir()
        and (path / "__init__.py").exists()
    ):
        _STD_LIB_MODULES.append(path.stem)


def _resolve_imported_value(
    app: Sphinx, env: BuildEnvironment, node: Element, contnode: TextElement
) -> Reference | Sentinel:
    if try_resolve_import_value(node["reftarget"], UNDEFINED) is not UNDEFINED:
        # If we can resolve just by trying to import it, then it's just undocumented.
        # This happens frequently for TypeVar definitions in annotations. This at least
        # validates that the reference truely exists.
        return SKIP

    py_domain: PythonDomain = env.domains["py"]

    origin_module: Any = import_module(node["py:module"])
    origin_ref_head, _, origin_ref_tail = node["reftarget"].partition(".")
    origin_value = getattr(origin_module, origin_ref_head, UNDEFINED)

    if origin_value is UNDEFINED:
        return UNDEFINED

    if isinstance(origin_value, ModuleType):
        # check if we can get this from intersphinx
        node["reftarget"] = f"{origin_value.__name__}.{origin_ref_tail}"
        ref = intersphinx_get_missing_ref(app, env, node, contnode)
        if ref is not None:
            return ref

    target_module_info = trace_import_to_source(origin_module, origin_ref_head)
    if target_module_info is None:
        return UNDEFINED
    target_module, target_ref_head = target_module_info

    target_value = getattr(target_module, target_ref_head, UNDEFINED)
    if origin_value is not target_value:
        return UNDEFINED

    class_name: str | None
    if origin_ref_tail:
        if isinstance(target_value, type):
            class_name = target_value.__name__
            qual_name = origin_ref_tail
        else:
            class_name = None
            qual_name = target_ref_head + "." + origin_ref_tail
    else:
        class_name = None
        qual_name = target_ref_head

    node["py:module"] = target_module.__name__
    node["py:class"] = class_name
    node["reftarget"] = qual_name

    ref = py_domain.resolve_xref(
        env,
        node["refdoc"],
        app.builder,
        node["reftype"],
        node["reftarget"],
        node,
        contnode,
    )

    if ref is None:
        origin_package_name = origin_module.__name__.split(".", 1)[0]
        target_package_name = target_module.__name__.split(".", 1)[0]
        is_external_target = origin_package_name != target_package_name
        return SKIP if is_external_target else UNDEFINED

    return ref


def _is_ref_to_external_package(node: Element) -> bool:
    if "." not in node["reftarget"]:
        return False

    origin_package: str = node["py:module"].split(".", 1)[0]
    target_package: str = node["reftarget"].split(".", 1)[0]

    try:
        is_namespace_package = not hasattr(import_module(target_package), "__file__")
    except ImportError:
        # is not package, or package does not exist
        return False

    if is_namespace_package:
        origin_package = node["py:module"].split(".", 2)[1]
        target_package = node["reftarget"].split(".", 2)[1]

    return origin_package != target_package
