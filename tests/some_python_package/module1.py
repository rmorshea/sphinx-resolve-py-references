"""Module 1"""

from .module2 import GLOBAL_2, GLOBAL_3, Class2, Class3, function_2, function_3


# convince flake8 we use these
Class2
Class3
function_2
function_3
GLOBAL_2
GLOBAL_3


class _UnDocType:
    ...


def func() -> _UnDocType:
    """
    - :class:`Class2`
    - :class:`Class3`
    - :func:`function_2`
    - :func:`function_3`
    - :data:`GLOBAL_2`
    - :data:`GLOBAL_3`
    """
