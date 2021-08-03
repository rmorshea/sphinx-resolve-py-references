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

import builtins
import distutils.sysconfig as sysconfig
import sys
from fnmatch import fnmatch as glob_match
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Any, Optional, Union

from docutils.nodes import Element, TextElement
from docutils.nodes import reference as Reference
from sphinx.application import Sphinx
from sphinx.domains.python import PythonDomain
from sphinx.environment import BuildEnvironment
from sphinx.ext.intersphinx import missing_reference as intersphinx_get_missing_ref
from sphinx.util import logging

from .utils import trace_import_to_source


logger = logging.getLogger(__name__)
UNDEFINED = object()
SKIP = object()


def resolve_py_reference(
    app: Sphinx, env: BuildEnvironment, node: Element, contnode: TextElement
) -> Optional[Reference]:
    if _skip_node(app, node):
        return None
    elif "py:module" not in node or node["py:module"] is None:
        if "refdoc" in node and node["refdoc"] != "api":
            src = node.source or node["refdoc"]
            msg = "No referent for name %r in %s"
            logger.warning(msg % (node["reftarget"], src))
        return None

    try:
        index_in_source = node.rawsource.index(node["reftarget"])
    except ValueError:
        return None

    is_relative = node.rawsource[index_in_source - 1 : index_in_source] == "."
    ref = _resolve_imported_value(app, env, node, contnode)

    if ref is None and not _is_ref_to_external_package(node):
        if node.source:
            src = f"{node.source!r} via module {node['py:module']!r}"
        else:
            src = node["py:module"]
        reftarget = node["reftarget"]
        if is_relative:
            reftarget = "." + reftarget
        logger.warning(f"No referent for name '{reftarget}' in {src}")
        return None
    elif ref is SKIP:
        return None
    else:
        return ref


def _skip_node(app: Sphinx, node: Element) -> bool:
    return (
        node["refdomain"] != "py"
        or any(
            glob_match(node["reftarget"], pattern)
            for pattern in app.config.allowed_missing_py_references
        )
        or node["reftarget"].split(".", 1)[0] in _STD_LIB_MODULES
        or hasattr(builtins, node["reftarget"])
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
) -> Union[None, Reference, Any]:
    py_domain: PythonDomain = env.domains["py"]

    origin_module: Any = import_module(node["py:module"])
    origin_ref_head, _, origin_ref_tail = node["reftarget"].partition(".")
    origin_value = getattr(origin_module, origin_ref_head, UNDEFINED)

    if origin_value is UNDEFINED:
        return None

    if isinstance(origin_value, ModuleType):
        # check if we can get this from intersphinx
        node["reftarget"] = f"{origin_value.__name__}.{origin_ref_tail}"
        ref = intersphinx_get_missing_ref(app, env, node, contnode)
        if ref is not None:
            return ref

    target_module, target_ref_head = trace_import_to_source(
        origin_module, origin_ref_head
    )

    if target_module is None or target_ref_head is None:
        return None

    target_value = getattr(target_module, target_ref_head, UNDEFINED)
    if origin_value is not target_value:
        return None

    class_name: Optional[str]
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
        if is_external_target:
            return SKIP

    return ref


def _is_ref_to_external_package(node):
    if "." not in node["reftarget"]:
        return False

    origin_package = node["py:module"].split(".", 1)[0]
    target_package = node["reftarget"].split(".", 1)[0]

    try:
        is_namespace_package = not hasattr(import_module(target_package), "__file__")
    except ImportError:
        # is not package, or package does not exist
        return False

    if is_namespace_package:
        origin_package = node["py:module"].split(".", 2)[1]
        target_package = node["reftarget"].split(".", 2)[1]

    return origin_package != target_package
