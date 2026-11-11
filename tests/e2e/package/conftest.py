"""Install the wheel under test outside the checkout and manage its lifetime."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest


def pytest_addoption(parser):
    group = parser.getgroup("package")
    group.addoption("--package-wheel", help="Built wheel to install for package E2E tests")
    group.addoption("--package-entrypoint", help="Console script provided by the wheel")


@pytest.fixture(scope="session")
def installed_package(request, tmp_path_factory):
    wheel = request.config.getoption("--package-wheel")
    entrypoint = request.config.getoption("--package-entrypoint")
    if not wheel or not entrypoint:
        pytest.fail("Package E2E tests require --package-wheel and --package-entrypoint")
    wheel = Path(wheel).resolve(strict=True)
    workdir = tmp_path_factory.mktemp("installed-package")
    venv = workdir / "venv"
    env = os.environ.copy()
    for name in ("PYTHONPATH", "VIRTUAL_ENV"):
        env.pop(name, None)
    subprocess.run(
        ["uv", "venv", "--python", "3.10", str(venv)],
        check=True, env=env, timeout=120,
    )
    python = venv / "bin" / "python"
    subprocess.run(
        ["uv", "pip", "install", "--python", str(python), str(wheel), "pytest"],
        check=True, env=env, timeout=180,
    )
    # Run the existing unit contract against the installed package as well.
    repo_root = Path(__file__).resolve().parents[3]
    shutil.copy(
        repo_root / "tests/unit/clients/test_error_report.py",
        workdir / "test_error_report.py",
    )
    try:
        yield {"python": python, "cli": venv / "bin" / entrypoint,
               "cwd": workdir, "env": env}
    finally:
        shutil.rmtree(workdir)
