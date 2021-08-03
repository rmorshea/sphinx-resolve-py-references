# sphinx-resolve-py-references

A sphinx extension that fixes or warns about missing references to Python objects

The extension is useful because it's often annoying to write out the full path to an
object in your docs which you know is imported in the current module. This is also true
for neighboring modules which would be easier referenced with a relative name.

This extension resolves these issues by allowing you to reference functions or classes
which are imported in the current module as if they had been defined there and creates
a backlink to their true location.

```python
from some_package import MyClass

def my_function():
    '''Uses :class:`MyClass`'''
    # The above reference would normally fail because `MyClass`
    # is not defined in this module. However this extension
    # automatically resolves the reference
```

This is done by analyzing the AST to find ``import`` statements and trace them back to
the place where the target was defined. This is more robust than looking at the
``__module__`` and ``__name__`` attributes of classes and functions because not all
documentable objects have these properties (e.g. global variables).
