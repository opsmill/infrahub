import subprocess  # noqa: S404
import sys


def test_module_imports_first_in_a_fresh_interpreter() -> None:
    # A test process has usually loaded the services package already, which would hide an import cycle.
    result = subprocess.run(
        args=[sys.executable, "-c", "import infrahub.workflows.initialization"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
