"""Replacement for Makefile."""
import os
import sys
import glob
from distutils.util import strtobool
from datetime import datetime

from typing import Tuple

from invoke import task, Context  # type: ignore

try:
    import toml
except ImportError:
    sys.exit("Please make sure to `pip install toml` or enable the Poetry shell and run `poetry install`.")

# flake8: noqa: W605


def project_ver() -> str:
    """Find version from pyproject.toml to use for docker image tagging."""
    with open("pyproject.toml", encoding="UTF-8") as file:
        return toml.load(file)["tool"]["poetry"].get("version", "latest")


def git_info(context: Context) -> Tuple[str, str]:
    """Return the name of the current branch and hash of the current commit."""
    branch_name = context.run("git rev-parse --abbrev-ref HEAD", hide=True, pty=False)
    hash = context.run("git rev-parse --short HEAD", hide=True, pty=False)
    return branch_name.stdout.strip(), hash.stdout.strip()


def is_truthy(arg):
    """Convert "truthy" strings into Booleans.

    Examples:
        >>> is_truthy('yes')
        True
    Args:
        arg (str): Truthy string (True values are y, yes, t, true, on and 1; false values are n, no,
        f, false, off and 0. Raises ValueError if val is anything else.
    """
    if isinstance(arg, bool):
        return arg
    return bool(strtobool(arg))


PYTHON_VER = os.getenv("PYTHON_VER", "3.9")
NAME = os.getenv("IMAGE_NAME", f"infrahub-py{PYTHON_VER}")
IMAGE_VER = os.getenv("IMAGE_VER", project_ver())
PWD = os.getcwd()
INVOKE_LOCAL = is_truthy(os.getenv("INVOKE_LOCAL", True))  # pylint: disable=W1508


def run_cmd(context, exec_cmd, name=NAME, image_ver=IMAGE_VER, local=INVOKE_LOCAL):
    """Wrapper to run the invoke task commands.

    Args:
        context ([invoke.task]): Invoke task object.
        exec_cmd ([str]): Command to run.
        name ([str], optional): Image name to use if exec_env is `docker`. Defaults to NAME.
        image_ver ([str], optional): Version of image to use if exec_env is `docker`. Defaults to IMAGE_VER.
        local (bool): Define as `True` to execute locally

    Returns:
        result (obj): Contains Invoke result from running task.
    """
    if is_truthy(local):
        print(f"LOCAL - Running command {exec_cmd}")
        result = context.run(exec_cmd, pty=True)
    else:
        print(f"DOCKER - Running command: {exec_cmd} container: {name}:{image_ver}")
        result = context.run(f"docker run -it -v {PWD}:/local {name}:{image_ver} sh -c '{exec_cmd}'", pty=True)

    return result


# @task
# def build(
#     context, name=NAME, python_ver=PYTHON_VER, image_ver=IMAGE_VER, nocache=False, forcerm=False
# ):  # pylint: disable=too-many-arguments
#     """This will build an image with the provided name and python version.

#     Args:
#         context (obj): Used to run specific commands
#         name (str): Used to name the docker image
#         python_ver (str): Define the Python version docker image to build from
#         image_ver (str): Define image version
#         nocache (bool): Do not use cache when building the image
#         forcerm (bool): Always remove intermediate containers
#     """
#     print(f"Building image {name}:{image_ver}")
#     command = f"docker build --tag {name}:{image_ver} --build-arg PYTHON_VER={python_ver} -f Dockerfile ."

#     if nocache:
#         command += " --no-cache"
#     if forcerm:
#         command += " --force-rm"

#     result = context.run(command, hide=False)
#     if result.exited != 0:
#         print(f"Failed to build image {name}:{image_ver}\nError: {result.stderr}")


# @task
# def clean_image(context, name=NAME, image_ver=IMAGE_VER):
#     """This will remove the specific image.

#     Args:
#         context (obj): Used to run specific commands
#         name (str): Used to name the docker image
#         image_ver (str): Define image version
#     """
#     print(f"Attempting to forcefully remove image {name}:{image_ver}")
#     context.run(f"docker rmi {name}:{image_ver} --force")
#     print(f"Successfully removed image {name}:{image_ver}")


# @task
# def rebuild(context, name=NAME, python_ver=PYTHON_VER, image_ver=IMAGE_VER):
#     """This will clean the image and then rebuild image without using cache.

#     Args:
#         context (obj): Used to run specific commands
#         name (str): Used to name the docker image
#         python_ver (str): Define the Python version docker image to build from
#         image_ver (str): Define image version
#     """
#     clean_image(context, name, image_ver)
#     build(context, name, python_ver, image_ver)


@task
def pytest(context, name=NAME, image_ver=IMAGE_VER, local=INVOKE_LOCAL):
    """This will run pytest for the specified name and Python version.

    Args:
        context (obj): Used to run specific commands
        name (str): Used to name the docker image
        image_ver (str): Will use the container version docker image
        local (bool): Define as `True` to execute locally
    """
    # pty is set to true to properly run the docker commands due to the invocation process of docker
    # https://docs.pyinvoke.org/en/latest/api/runners.html - Search for pty for more information
    # Install python module
    exec_cmd = "pytest --cov=diffsync --cov-config pyproject.toml --cov-report html --cov-report term -vv"
    run_cmd(context, exec_cmd, name, image_ver, local)


@task
def black(context, name=NAME, image_ver=IMAGE_VER, local=INVOKE_LOCAL):
    """This will run black to check that Python files adherence to black standards.

    Args:
        context (obj): Used to run specific commands
        name (str): Used to name the docker image
        image_ver (str): Define image version
        local (bool): Define as `True` to execute locally
    """
    # pty is set to true to properly run the docker commands due to the invocation process of docker
    # https://docs.pyinvoke.org/en/latest/api/runners.html - Search for pty for more information
    exec_cmd = "black --check --diff ."
    run_cmd(context, exec_cmd, name, image_ver, local)


@task
def flake8(context, name=NAME, image_ver=IMAGE_VER, local=INVOKE_LOCAL):
    """This will run flake8 for the specified name and Python version.

    Args:
        context (obj): Used to run specific commands
        name (str): Used to name the docker image
        image_ver (str): Define image version
        local (bool): Define as `True` to execute locally
    """
    # pty is set to true to properly run the docker commands due to the invocation process of docker
    # https://docs.pyinvoke.org/en/latest/api/runners.html - Search for pty for more information
    exec_cmd = "flake8 ."
    run_cmd(context, exec_cmd, name, image_ver, local)


@task
def mypy(context, name=NAME, image_ver=IMAGE_VER, local=INVOKE_LOCAL):
    """This will run mypy for the specified name and Python version.

    Args:
        context (obj): Used to run specific commands
        name (str): Used to name the docker image
        image_ver (str): Define image version
        local (bool): Define as `True` to execute locally
    """
    # pty is set to true to properly run the docker commands due to the invocation process of docker
    # https://docs.pyinvoke.org/en/latest/api/runners.html - Search for pty for more information
    exec_cmd = 'find . -name "*.py" -not -path "*/examples/*" -not -path "*/docs/*" | xargs mypy --show-error-codes'
    run_cmd(context, exec_cmd, name, image_ver, local)


@task
def pylint(context, name=NAME, image_ver=IMAGE_VER, local=INVOKE_LOCAL):
    """This will run pylint for the specified name and Python version.

    Args:
        context (obj): Used to run specific commands
        name (str): Used to name the docker image
        image_ver (str): Define image version
        local (bool): Define as `True` to execute locally
    """
    # pty is set to true to properly run the docker commands due to the invocation process of docker
    # https://docs.pyinvoke.org/en/latest/api/runners.html - Search for pty for more information
    exec_cmd = 'find . -name "*.py" | xargs pylint'
    run_cmd(context, exec_cmd, name, image_ver, local)


@task
def yamllint(context, name=NAME, image_ver=IMAGE_VER, local=INVOKE_LOCAL):
    """This will run yamllint to validate formatting adheres to NTC defined YAML standards.

    Args:
        context (obj): Used to run specific commands
        name (str): Used to name the docker image
        image_ver (str): Define image version
        local (bool): Define as `True` to execute locally
    """
    # pty is set to true to properly run the docker commands due to the invocation process of docker
    # https://docs.pyinvoke.org/en/latest/api/runners.html - Search for pty for more information
    exec_cmd = "yamllint ."
    run_cmd(context, exec_cmd, name, image_ver, local)


@task
def pydocstyle(context, name=NAME, image_ver=IMAGE_VER, local=INVOKE_LOCAL):
    """This will run pydocstyle to validate docstring formatting adheres to NTC defined standards.

    Args:
        context (obj): Used to run specific commands
        name (str): Used to name the docker image
        image_ver (str): Define image version
        local (bool): Define as `True` to execute locally
    """
    # pty is set to true to properly run the docker commands due to the invocation process of docker
    # https://docs.pyinvoke.org/en/latest/api/runners.html - Search for pty for more information
    exec_cmd = "pydocstyle ."
    run_cmd(context, exec_cmd, name, image_ver, local)


@task
def neo4j_start(context):
    """Start a local instance of NEO4J.

    Args:
        context (obj): Used to run specific commands
    """
    # pty is set to true to properly run the docker commands due to the invocation process of docker
    # https://docs.pyinvoke.org/en/latest/api/runners.html - Search for pty for more information
    exec_cmd = """docker run --name neo4j-dev \
                -p 7474:7474 -p 7687:7687 \
                --env NEO4J_ACCEPT_LICENSE_AGREEMENT=yes \
                --env NEO4J_dbms_security_procedures_unrestricted=apoc.\\\* \
                --env NEO4J_PLUGINS=\[\"apoc\"\] \
                --env NEO4J_AUTH=neo4j/admin \
                -d --rm neo4j:5.1-enterprise
                """
    context.run("docker rm neo4j-dev", pty=False, warn=True)
    return context.run(exec_cmd, pty=True)


@task
def neo4j_stop(context):
    """Stop the local instance of NEO4J.

    Args:
        context (obj): Used to run specific commands
    """
    # pty is set to true to properly run the docker commands due to the invocation process of docker
    # https://docs.pyinvoke.org/en/latest/api/runners.html - Search for pty for more information
    exec_cmd = "docker stop neo4j-dev"
    _ = context.run(exec_cmd, pty=True)


@task
def rabbitmq_start(context):
    """Start a local instance of RabbitMQ.

    Args:
        context (obj): Used to run specific commands
    """
    # pty is set to true to properly run the docker commands due to the invocation process of docker
    # https://docs.pyinvoke.org/en/latest/api/runners.html - Search for pty for more information
    exec_cmd = """docker run --name rabbitmq-dev \
                -d -p 5672:5672 \
                -p 15672:15672 \
                rabbitmq:3-management
                """
    context.run("docker rm rabbitmq-dev", pty=False, warn=True)
    return context.run(exec_cmd, pty=True)


@task
def rabbitmq_stop(context):
    """Stop the local instance of RabbitMQ.

    Args:
        context (obj): Used to run specific commands
    """
    # pty is set to true to properly run the docker commands due to the invocation process of docker
    # https://docs.pyinvoke.org/en/latest/api/runners.html - Search for pty for more information
    exec_cmd = "docker stop rabbitmq-dev"
    result = context.run(exec_cmd, pty=True)


@task
def performance_test(context, directory="utilities", dataset="dataset03"):

    PERFORMANCE_FILE_PREFIX = "locust_"
    NOW = datetime.now()
    date_format = NOW.strftime("%Y-%m-%d-%H-%M-%S")

    local_dir = os.path.dirname(os.path.abspath(__file__))
    test_files = glob.glob(f"{local_dir}/{directory}/{PERFORMANCE_FILE_PREFIX}{dataset}*.py")

    branch_name, hash = git_info(context)

    for test_file in test_files:
        cmd = f"locust -f {test_file} --host=http://localhost:8000 --headless --reset-stats -u 2 -r 2 -t 20s --only-summary"
        result = context.run(cmd, pty=True)

        result_file_name = f"{local_dir}/{directory}/summary_{dataset}_{branch_name}_{hash}_{date_format}.txt"
        with open(result_file_name, "w") as f:
            print(result.stdout, file=f)


@task
def tests(context, name=NAME, image_ver=IMAGE_VER, local=INVOKE_LOCAL):
    """This will run all tests for the specified name and Python version.

    Args:
        context (obj): Used to run specific commands
        name (str): Used to name the docker image
        image_ver (str): Define image version
        local (bool): Define as `True` to execute locally
    """
    black(context, name, image_ver, local)
    flake8(context, name, image_ver, local)
    pylint(context, name, image_ver, local)
    yamllint(context, name, image_ver, local)
    pydocstyle(context, name, image_ver, local)
    mypy(context, name, image_ver, local)
    pytest(context, name, image_ver, local)

    print("All tests have passed!")
