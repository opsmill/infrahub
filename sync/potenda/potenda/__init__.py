from typing import List, Optional

from diffsync import DiffSync
from diffsync.diff import Diff
from diffsync.enum import DiffSyncFlags
from diffsync.logging import enable_console_logging
from infrahub_sync import SyncInstance


class Potenda:
    def __init__(
        self,
        source: DiffSync,
        destination: DiffSync,
        config: SyncInstance,
        top_level: List[str],
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

    def diff(self) -> Diff:
        print(f"Diff: Comparing data from {self.source} to {self.destination}")
        return self.destination.diff_from(self.source, flags=self.flags)

    @classmethod
    def _print_callback(self, stage: str, elements_processed: int, total_models: int):
        """Callback for DiffSync"""
        percentage: float = round(elements_processed / total_models * 100, 1)
        if percentage.is_integer():
            print(f"-> Processed {elements_processed} on {total_models} ({percentage}% done)")

    def sync(self, diff: Optional[Diff] = None):
        print(f"Sync: Importing data from {self.source} to {self.destination} based on Diff")
        return self.destination.sync_from(self.source, diff=diff, flags=self.flags, callback=self._print_callback)
