import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from git.repo import Repo

from infrahub.exceptions import InitializationError

from .fixtures import get_fixtures_dir


@dataclass
class FileRepo:
    name: str
    sources_directory: Path
    _repo: Optional[Repo] = None
    _initial_branch: Optional[str] = None
    _branches: list[str] = field(default_factory=list)

    @property
    def repo(self) -> Repo:
        if self._repo:
            return self._repo
        raise InitializationError

    def _initial_directory(self, repo_base: Path) -> str:
        initial_candidates = list(repo_base.glob("initial__*"))
        assert len(initial_candidates) == 1
        initial_directory = str(initial_candidates[0]).replace(f"{repo_base}/", "")
        _, branch = initial_directory.split("__")
        self._initial_branch = self._initial_branch or branch
        self._branches.append(self._initial_branch)
        return initial_directory

    def _apply_pull_requests(self, repo_base: Path) -> None:
        pull_requests = sorted(list(repo_base.glob("pr*")))
        for pull_request in pull_requests:
            branch = str(pull_request).split("__")[-1]
            if branch in self._branches:
                self.repo.git.checkout(self._initial_branch)
            else:
                self._branches.append(branch)
                self.repo.git.checkout("-b", branch)
            shutil.copytree(pull_request, self.sources_directory / self.name, dirs_exist_ok=True)
            self.repo.git.add(".")
            self.repo.git.commit("-m", pull_request)

    def __post_init__(self) -> None:
        repo_base = Path(get_fixtures_dir(), "repos", self.name)
        initial_directory = self._initial_directory(repo_base=repo_base)
        shutil.copytree(repo_base / initial_directory, self.sources_directory / self.name)
        self._repo = Repo.init(self.sources_directory / self.name, initial_branch=self._initial_branch)
        for untracked in self.repo.untracked_files:
            self.repo.index.add(untracked)
        self.repo.index.commit("First commit")

        self._apply_pull_requests(repo_base=repo_base)
        self.repo.git.checkout(self._initial_branch)

    @property
    def path(self) -> str:
        return str(os.path.join(self.sources_directory, self.name))
