import glob
import os
from datetime import datetime, timezone

from invoke import Context, task

from .utils import git_info


@task
def run(context: Context, directory: str = "utilities", dataset: str = "dataset03"):
    """Launch a performance test using Locust. Gunicorn must be running"""
    PERFORMANCE_FILE_PREFIX = "locust_"
    NOW = datetime.now(tz=timezone.utc)
    date_format = NOW.strftime("%Y-%m-%d-%H-%M-%S")

    local_dir = os.path.dirname(os.path.abspath(__file__))
    test_files = glob.glob(f"{local_dir}/{directory}/{PERFORMANCE_FILE_PREFIX}{dataset}*.py")

    branch_name, hash = git_info(context)  # pylint: disable=redefined-builtin

    for test_file in test_files:
        cmd = f"locust -f {test_file} --host=http://localhost:8000 --headless --reset-stats -u 2 -r 2 -t 20s --only-summary"
        result = context.run(cmd, pty=True)

        result_file_name = f"{local_dir}/{directory}/summary_{dataset}_{branch_name}_{hash}_{date_format}.txt"
        with open(result_file_name, "w", encoding="UTF-8") as f:
            print(result.stdout, file=f)
