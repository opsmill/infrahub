from typing import List, Optional

from diffsync import DiffSync
from diffsync.diff import Diff
from diffsync.enum import DiffSyncFlags
from diffsync.logging import enable_console_logging
from tqdm import tqdm

from infrahub_sync import SyncInstance


class Potenda:
    def __init__(
        self,
        source: DiffSync,
        destination: DiffSync,
        config: SyncInstance,
        top_level: List[str],
        partition=None,
        show_progress: Optional[bool] = False,
    ):
        self.top_level = top_level

        self.config = config

        self.source = source
        self.destination = destination

        self.source.top_level = top_level
        self.destination.top_level = top_level

        self.partition = partition
        self.progress_bar = None
        self.show_progress = show_progress
        enable_console_logging(verbosity=1)
        self.flags = DiffSyncFlags.SKIP_UNMATCHED_DST

    def _print_callback(self, stage: str, elements_processed: int, total_models: int):
        """Callback for DiffSync using tqdm"""
        if self.show_progress:
            if self.progress_bar is None:
                self.progress_bar = tqdm(total=total_models, desc=stage, unit="models")

            self.progress_bar.n = elements_processed
            self.progress_bar.refresh()

            if elements_processed == total_models:
                self.progress_bar.close()
                self.progress_bar = None

    def source_load(self):
        try:
            print(f"Load: Importing data from {self.source}")
            self.source.load()
        except Exception as exc:
            raise Exception(f"An error occurred while loading {self.source}: {exc}")

    def destination_load(self):
        try:
            print(f"Load: Importing data from {self.destination}")
            self.destination.load()
        except Exception as exc:
            raise Exception(f"An error occurred while loading {self.destination}: {exc}")

    def load(self):
        try:
            self.source_load()
            self.destination_load()
        except Exception as exc:
            raise Exception(f"An error occurred while loading the sync: {exc}")

    def diff(self) -> Diff:
        print(f"Diff: Comparing data from {self.source} to {self.destination}")
        self.progress_bar = None
        return self.destination.diff_from(self.source, flags=self.flags, callback=self._print_callback)

    def sync(self, diff: Optional[Diff] = None):
        print(f"Sync: Importing data from {self.source} to {self.destination} based on Diff")
        self.progress_bar = None
        return self.destination.sync_from(self.source, diff=diff, flags=self.flags, callback=self._print_callback)
