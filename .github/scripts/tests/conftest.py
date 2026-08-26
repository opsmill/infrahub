import sys
from pathlib import Path

# The scripts live outside any package, so put their directory on sys.path for the tests.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
