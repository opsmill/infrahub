import glob
import logging
import os
import signal
import sys
import time
from pathlib import Path

import git
import typer
import yaml
from git import Repo
from rich.logging import RichHandler

import infrahub.config as config
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import initialization
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node

app = typer.Typer()

logging.getLogger("neo4j").setLevel(logging.ERROR)
logging.getLogger("git").setLevel(logging.ERROR)


def signal_handler(signal, frame):
    print("\nWorker terminated by user.")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


def import_all_graphql_query(log, repo, branch, search_directory):
    """Search for all .gql file and import them as GraphQL query."""

    for query_file in glob.glob(f"{search_directory}/**/*.gql", recursive=True):

        filename = os.path.basename(query_file)
        query_name = os.path.splitext(filename)[0]

        queries = NodeManager.query("GraphQLQuery", filters={"name__value": query_name}, branch=branch)

        query_string = Path(query_file).read_text()
        if queries:
            query = queries[0]

            if query.query.value != query_string:
                log.info(
                    f"{repo.name.value}: New version of the Graphql Query '{query_name}' found on branch {branch.name}, updating"
                )
                query.query.value = query_string
                query.save()

        else:
            log.info(f"{repo.name.value}: New Graphql Query '{query_name}' found on branch {branch.name}, creating")
            query = (
                Node("GraphQLQuery", branch=branch).new(name=query_name, query=query_string).save()
            )  # source=repo.get_account())


def import_rfile(log, repo, branch, data):

    for rfile_name, rfile in data.items():

        rfile_schema = registry.get_schema("RFile")
        items = NodeManager.query(rfile_schema, filters={rfile_schema.default_filter: rfile_name}, branch=branch)
        item = items[0] if items else None

        # Insert the UUID of the repository in case they are referencing the local repo
        for key in rfile.keys():
            if "repository" in key:
                if rfile[key] == "self":
                    rfile[key] = repo.id

        if not item:
            log.info(f"{repo.name.value}: New RFile '{rfile_name}' found on branch {branch.name}, creating")
            item = Node(rfile_schema, branch=branch).new(name=rfile_name, **rfile).save()  # source=repo.get_account(),
        else:
            need_to_update = False
            for field_name in ["output_path", "template_path", "description"]:
                attr = getattr(item, field_name)
                if field_name in rfile and rfile[field_name] != attr.value:
                    attr.value = rfile[field_name]
                    need_to_update = True

            if need_to_update:
                log.info(
                    f"{repo.name.value}: New version of the RFile '{rfile_name}' found on branch {branch.name}, updating"
                )
                item.save()


def import_device(log, repo, branch, data):
    pass


def import_all_yaml_files(log, repo, branch, search_directory):

    VALID_OBJECTS = {
        "rfiles": import_rfile,
        "device": import_device,
    }

    yaml_files = glob.glob(f"{search_directory}/**/*.yml", recursive=True) + glob.glob(
        f"{search_directory}/**/.*.yml", recursive=True
    )

    for yaml_file in yaml_files:

        # log.debug(f"{repo.name.value}: Checking {yaml_file}")

        # ------------------------------------------------------
        # Import Yaml
        # ------------------------------------------------------
        with open(yaml_file, "r") as file_data:
            yaml_data = file_data.read()

        try:
            data = yaml.safe_load(yaml_data)
        except yaml.YAMLError as exc:
            log.warning(f"{repo.name.value}: Unable to load YAML file {yaml_file} : {exc.message}")
            continue

        if not isinstance(data, dict):
            log.debug(f"{repo.name.value}: {yaml_file} : payload is not a dictionnary .. SKIPPING")
            continue

        # ------------------------------------------------------
        # Search for Valid object types
        # ------------------------------------------------------
        for key, data in data.items():
            if key not in VALID_OBJECTS.keys():
                continue

            VALID_OBJECTS[key](log, repo, branch, data)


@app.command()
def start(
    interval: int = 10,
    debug: bool = False,
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
):

    log_level = "DEBUG" if debug else "INFO"

    FORMAT = "%(message)s"
    logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])
    log = logging.getLogger("infrahub.worker")

    log.debug(f"Config file : {config_file}")

    config.load_and_exit(config_file_name=config_file)
    initialization()

    log.info(f"Watching for repositories in {config.SETTINGS.main.repositories_directory}")

    # Run in continuous mode
    # - For each repository
    #   - Pull the latest information from origin and check if the commit on all branches match what we have in the database
    #   - If there is a new commit, update the commit and check what needs to be imported
    # Delete worktree for branches that are not present anymore
    # Check for uncommited files in the repo and remove them

    # Current Assumptions
    # - Repos must have only 1 remote named origin

    while True:

        # ----------------------------------------------------------------------
        # House Keeping
        # -----------------------------------------------------------------------
        # Ensure the paths to the directory is an absolute path
        current_dir = os.getcwd()
        repositories_directory = config.SETTINGS.main.repositories_directory
        if not os.path.isabs(repositories_directory):
            repositories_directory = os.path.join(current_dir, config.SETTINGS.main.repositories_directory)

        # Create the directory if the directory doesn't exist
        isdir = os.path.isdir(repositories_directory)
        if not isdir:
            os.makedirs(repositories_directory)

        # ----------------------------------------------------------------------
        # Check all repos on the main branch
        # -----------------------------------------------------------------------
        main_branch = Branch.get_by_name(config.SETTINGS.main.default_branch)
        branches = Branch.get_list()
        db_branche_names = [item.name for item in branches]

        for repo in NodeManager.query("Repository", branch=main_branch):

            log.debug(f"{repo.name.value} in branch {main_branch.name}")

            repo.ensure_exists_locally()

            git_repo = repo.get_git_repo_main()

            # Pull the latest update from the remote repo
            git_repo.remotes.origin.fetch()
            git_repo.remotes.origin.pull()
            if str(git_repo.head.commit) != str(repo.commit.value):
                log.info(
                    f"{repo.name.value}: Commit on branch {repo._branch.name} ({repo.commit.value}) do not match the local value ({git_repo.head.commit})"
                )

                repo.commit.value = str(git_repo.head.commit)
                repo.save()

            # Remove stale branches from the remote repo
            for stale_branch in git_repo.remotes.origin.stale_refs:
                if not isinstance(stale_branch, git.refs.remote.RemoteReference):
                    continue

                log.debug(f"{repo.name.value}: Cleaning branch {stale_branch.name} no longer present on remote.")
                type(stale_branch).delete(git_repo, stale_branch)

            # Got over all branches in the remote and check if they already exist locally
            # If not, create a new branch locally in the database and in Git and track the remote branch
            for remote_branch in git_repo.remotes.origin.refs:
                if not isinstance(remote_branch, git.refs.remote.RemoteReference):
                    continue
                short_name = remote_branch.name.replace("origin/", "")

                if short_name == "HEAD" or short_name in db_branche_names:
                    continue

                log.info(f"{repo.name.value}: Found new branch {short_name}")

                # Create the new branch in the database
                # Don't do more for now because we'll process all other repos in the next section
                new_branch = Branch(name=short_name, description=f"Created from Repository: {repo.name.value}")
                new_branch.save()

                # Create the new Branch locally in Git too
                local_branch_names = [br.name for br in git_repo.refs if not br.is_remote()]
                if short_name not in local_branch_names:
                    git_repo.git.branch(short_name)

            # IMPORT DATA FROM REPOSITORY / BRANCH
            import_all_graphql_query(log=log, repo=repo, branch=main_branch, search_directory=repo.directory_default)

            import_all_yaml_files(log=log, repo=repo, branch=main_branch, search_directory=repo.directory_default)

            # TODO - CLEANUP
            #  * CHECK if all worktree match with existing branches
            #  * Find a way to match worktree based on commit to clean them as well

        for branch in Branch.get_list():
            if branch.name == config.SETTINGS.main.default_branch:
                continue

            if branch.is_data_only:
                continue

            for repo in NodeManager.query("Repository", branch=branch):

                # Check if the repository for the branch exist locally
                log.debug(f"{repo.name.value} in branch {branch.name}")

                if not os.path.isdir(repo.directory_branch):
                    main_repo = Repo(repo.directory_default)

                    local_branch_names = [br.name for br in main_repo.refs if not br.is_remote()]
                    if branch.name not in local_branch_names:
                        main_repo.git.branch(branch.name)

                    # TODO we probably need to check the worktree too at some point
                    main_repo.git.worktree("add", repo.directory_branch, branch.name)

                git_repo = Repo(repo.directory_branch)

                # Check if the worktree has been configure to track a specific branch
                if not git_repo.active_branch.tracking_branch():
                    remote_branch = [br for br in git_repo.remotes.origin.refs if br.name == f"origin/{branch.name}"]
                    if remote_branch:
                        git_repo.head.reference.set_tracking_branch(remote_branch[0])
                        git_repo.remotes.origin.pull()
                else:
                    git_repo.remotes.origin.pull()

                if str(git_repo.head.commit) != str(repo.commit.value):
                    log.info(
                        f"{repo.name.value}: Commit on branch {repo._branch.name} has been updated ({git_repo.head.commit})"
                    )
                    repo.commit.value = str(git_repo.head.commit)
                    repo.save()

                # IMPORT DATA FROM REPOSITORY / BRANCH
                import_all_graphql_query(log=log, repo=repo, branch=branch, search_directory=repo.directory_branch)
                import_all_yaml_files(log=log, repo=repo, branch=branch, search_directory=repo.directory_branch)

        time.sleep(interval)
