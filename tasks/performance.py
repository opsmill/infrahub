from datetime import datetime, timezone
from pathlib import Path

from invoke import Context, task

from .utils import git_info


@task
def run(context: Context, directory: str = "utilities", dataset: str = "dataset03") -> None:
    """Launch a performance test using Locust. Gunicorn must be running"""
    PERFORMANCE_FILE_PREFIX = "locust_"
    NOW = datetime.now(tz=timezone.utc)
    date_format = NOW.strftime("%Y-%m-%d-%H-%M-%S")

    local_dir = Path(__file__).parent.resolve()
    test_files = (local_dir / directory).glob(f"{PERFORMANCE_FILE_PREFIX}{dataset}*.py")

    branch_name, git_hash = git_info(context)

    for test_file in test_files:
        cmd = f"locust -f {test_file} --host=http://localhost:8000 --headless --reset-stats -u 2 -r 2 -t 20s --only-summary"
        result = context.run(cmd)

        result_file_name = Path(local_dir, directory, f"summary_{dataset}_{branch_name}_{git_hash}_{date_format}.txt")
        result_file_name.write_text(result.stdout, encoding="utf-8")
