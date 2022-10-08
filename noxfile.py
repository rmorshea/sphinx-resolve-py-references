from pathlib import Path

import nox


HERE = Path(__file__).parent


@nox.session
def test(session: nox.Session) -> None:
    ...


@nox.session
def test(session: nox.Session) -> None:
    """Run the complete test suite"""
    session.install("--upgrade", "pip", "setuptools", "wheel")
    session.notify("test_suite")
    session.notify("test_style")
    session.notify("test_types")


@nox.session
def test_types(session: nox.Session) -> None:
    install_requirements_file(session, "check-types")
    session.run(
        "mypy",
        "--strict",
        "--show-error-codes",
        "src/sphinx_resolve_py_references",
    )


@nox.session
def test_suite(session: nox.Session) -> None:
    """Run the Python-based test suite"""
    install_requirements_file(session, "test-env")
    session.install("-e", ".")

    session.chdir("tests")
    session.run(
        "rm",
        "-rf",
        str(Path("tests") / "build"),
        external=True,
    )
    session.run(
        "sphinx-apidoc",
        "some_python_package",
        "-f",
        "-o",
        str(Path("source") / "generated"),
        env={"PYTHONPATH": "."},
    )
    session.run(
        "sphinx-build",
        "-a",  # re-write all output files
        "-T",  # show full tracebacks
        "-W",  # turn warnings into errors
        "--keep-going",  # complete the build, but still report warnings as errors
        "-b",
        "html",
        "source",
        "build",
    )


@nox.session
def test_style(session: nox.Session) -> None:
    """Check that style guidelines are being followed"""
    install_requirements_file(session, "check-style")
    session.run("flake8", "src", "tests")
    black_default_exclude = r"\.eggs|\.git|\.hg|\.mypy_cache|\.nox|\.tox|\.venv|\.svn|_build|buck-out|build|dist"
    session.run(
        "black",
        ".",
        "--check",
        "--exclude",
        rf"/({black_default_exclude}|venv)/",
    )
    session.run("isort", ".", "--check-only")


def install_requirements_file(session: nox.Session, name: str) -> None:
    file_path = HERE / "requirements" / (name + ".txt")
    assert file_path.exists(), f"requirements file {file_path} does not exist"
    session.install("-r", str(file_path))
