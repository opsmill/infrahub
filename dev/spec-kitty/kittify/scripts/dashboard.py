#!/usr/bin/env python3
"""SpecKitty Dashboard launcher.

Delegates to the full dashboard server in dashboard/server.py.
Kept for backwards compatibility with existing scripts.
"""

from __future__ import annotations

import os
import subprocess  # noqa: S404
import sys
from pathlib import Path


def main() -> None:
    server_script = Path(__file__).resolve().parent / "dashboard" / "server.py"
    if not server_script.exists():
        print(f"Error: dashboard server not found at {server_script}", file=sys.stderr)
        sys.exit(1)

    # Forward all arguments
    cmd = [sys.executable, str(server_script), *sys.argv[1:]]
    try:
        os.execvp(sys.executable, cmd)  # noqa: S606
    except OSError:
        # Fallback for platforms where execvp fails
        result = subprocess.run(cmd, check=False)  # noqa: S603
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
