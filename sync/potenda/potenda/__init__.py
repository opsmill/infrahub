from diffsync.enum import DiffSyncFlags
from diffsync.logging import enable_console_logging


class Potenda:
    def __init__(
        self,
        source,
        destination,
        config,
        top_level,
        partition=None,
    ):
        self.top_level = top_level

        self.config = config

        self.source = source
        self.destination = destination

        self.source.top_level = top_level
        self.destination.top_level = top_level

        self.partition = partition

        self.flags = DiffSyncFlags.SKIP_UNMATCHED_DST

        enable_console_logging(verbosity=1)

    def load(self):
        try:
            print(f"Load: Importing data from {self.source}")
            self.source.load()
            print(f"Load: Importing data from {self.destination}")
            self.destination.load()
        except Exception as e:
            raise Exception(f"An error occurred while loading the sync: {e}")

    def diff(self):
        print(f"Diff: Comparing data from {self.source} to {self.destination}")
        return self.destination.diff_from(self.source, flags=self.flags)

    def sync(self, diff):
        print(f"Sync: Importing data from {self.source} to {self.destination} based on Diff")
        return self.destination.sync_from(self.source, diff=diff, flags=self.flags)
