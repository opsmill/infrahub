import shutil
from dataclasses import dataclass, field
from pathlib import Path

from git.repo import Repo

from infrahub.exceptions import InitializationError

from .fixtures import get_fixtures_dir


@dataclass
class FileRepo:
    name: str
    sources_directory: Path

    # Some tests make a prior copy of fixtures/repos/car-dealership folder in a temp folder,
    # in which case we need to use that temp folder instead of fixture dir. This could probably be removed
    # when https://github.com/opsmill/infrahub/issues/4296 is fixed.
    local_repo_base_path: Path = get_fixtures_dir() / "repos"

    _repo: Repo | None = None
    _initial_branch: str | None = None
    _branches: list[str] = field(default_factory=list)

    @property
    def repo(self) -> Repo:
        if self._repo:
            return self._repo
        raise InitializationError

    def _initial_directory(self, repo_base: Path) -> str:
        initial_candidates = list(repo_base.glob("initial__*"))
        assert len(initial_candidates) == 1

        initial_directory = str(initial_candidates[0].relative_to(repo_base))
        _, branch = initial_directory.split("__")

        self._initial_branch = self._initial_branch or branch
        self._branches.append(self._initial_branch)
        return initial_directory

    def _apply_pull_requests(self, repo_base: Path) -> None:
        pull_requests = sorted(repo_base.glob("pr*"))
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
        repo_base = Path(self.local_repo_base_path, self.name)
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
        return str(self.sources_directory / self.name)


@dataclass
class MultipleStagesFileRepo(FileRepo):
    """Redefines methods to support more complex repository workflow with multiple commits and branching with these."""

    def _initial_directory(self, repo_base: Path) -> str:
        initial_candidates = list(repo_base.glob("initial__*"))
        assert len(initial_candidates) == 1

        initial_directory = str(initial_candidates[0].relative_to(repo_base))
        _, branch = initial_directory.split("__")

        self._initial_branch = self._initial_branch or branch
        self._branches.append(self._initial_branch)

        return initial_directory

    def _setup_initial_branch(self, directory: Path) -> None:
        """Setup the initial branch with multiple commits."""
        initial_commit_folders = sorted(directory.glob("commit*"))
        for i, commit_folder in enumerate(initial_commit_folders, start=1):
            shutil.copytree(commit_folder, self.sources_directory / self.name, dirs_exist_ok=True)
            self.repo.git.add(".")
            self.repo.index.commit(f"Step {i}")
            # Tag commit for later reference
            self.repo.create_tag(f"{self._initial_branch}-step{i}")

    def _apply_pull_requests(self, repo_base: Path) -> None:
        pull_requests = sorted(repo_base.glob("pr*"))
        for pull_request in pull_requests:
            branch = str(pull_request).split("__")[-1]
            base_commit_path = pull_request / "base_commit"
            base_commit: str | None = None

            if base_commit_path.exists():
                base_commit = base_commit_path.read_text().strip()

            if branch in self._branches:
                self.repo.git.checkout(branch)
            else:
                # Checkout the base commit or fallback to the initial branch
                self.repo.git.checkout(base_commit or self._initial_branch)
                self.repo.git.checkout("-b", branch)
                self._branches.append(branch)

            # Apply changes and create multiple commits if specified
            commit_folders = sorted(pull_request.glob("commit*"))
            for i, commit_folder in enumerate(commit_folders, start=1):
                shutil.copytree(commit_folder, self.sources_directory / self.name, dirs_exist_ok=True)
                self.repo.git.add(".")
                self.repo.git.commit("-m", f"{pull_request} step {i}")

    def __post_init__(self) -> None:
        repo_base = self.local_repo_base_path / self.name
        initial_directory = self._initial_directory(repo_base=repo_base)

        shutil.copytree(repo_base / initial_directory, self.sources_directory / self.name)
        self._repo = Repo.init(self.sources_directory / self.name, initial_branch=self._initial_branch)

        self._setup_initial_branch(directory=repo_base / initial_directory)
        self._apply_pull_requests(repo_base=repo_base)

        self.repo.git.checkout(self._initial_branch)
