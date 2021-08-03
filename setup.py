import sys
from pathlib import Path

from setuptools import find_packages, setup


# the name of the project
name = "sphinx_resolve_py_references"

# basic paths used to gather files
root_dir = Path(__file__).parent
src_dir = root_dir / "src"
package_dir = src_dir / name


# -----------------------------------------------------------------------------
# Package Definition
# -----------------------------------------------------------------------------


package = {
    "name": name,
    "python_requires": ">=3.7",
    "packages": find_packages(str(src_dir)),
    "package_dir": {"": "src"},
    "description": "Better python object resolution in Sphinx",
    "author": "Ryan Morshead",
    "author_email": "ryan.morshead@gmail.com",
    "url": "https://github.com/23andMe/sphinx-resolve-py-references",
    "license": "BSD",
    "platforms": "Linux, Mac OS X, Windows",
    "keywords": ["Sphinx"],
    "zip_safe": False,
    "classifiers": [
        " Framework :: Sphinx :: Extension",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    "options": {
        "bdist_wheel": {"universal":True},
    },
}


# -----------------------------------------------------------------------------
# Library Version
# -----------------------------------------------------------------------------

package_init_file = package_dir / "__init__.py"
with package_init_file.open() as f:
    for line in f.read().split("\n"):
        if line.startswith("__version__ = "):
            package["version"] = eval(line.split("=", 1)[1])
            break
    else:
        print(f"No '__version__' declared in {package_init_file}")
        sys.exit(1)


# -----------------------------------------------------------------------------
# Requirements
# -----------------------------------------------------------------------------


requirements = []
with (root_dir / "requirements" / "pkg-deps.txt").open() as f:
    for line in map(str.strip, f):
        if not line.startswith("#"):
            requirements.append(line)
package["install_requires"] = requirements


# -----------------------------------------------------------------------------
# Library Description
# -----------------------------------------------------------------------------


with (root_dir / "README.md").open() as f:
    long_description = f.read()

package["long_description"] = long_description
package["long_description_content_type"] = "text/markdown"


# -----------------------------------------------------------------------------
# Install It
# -----------------------------------------------------------------------------


if __name__ == "__main__":
    setup(**package)
