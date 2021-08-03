from sphinx.application import Sphinx

from .resolver import resolve_py_reference


def setup(app: Sphinx):
    app.connect("missing-reference", resolve_py_reference)
    app.add_config_value("allowed_missing_py_references", [], "env")
