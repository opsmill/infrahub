from pathlib import Path

from prefect import flow
from prefect.logging import get_run_logger

from infrahub.marketplace.models import MarketplaceInstallModel
from infrahub.services.adapters.http.httpx import HttpxAdapter
from infrahub.workers.dependencies import get_client


@flow(
    name="marketplace-schema-install",
    flow_run_name="Installing marketplace schemas to branch {model.branch_name}",
)
async def install_marketplace_schemas(model: MarketplaceInstallModel) -> None:
    """Download marketplace schemas via REST API, commit them to a Git repository, and push to remote."""
    from infrahub.git.repository import InfrahubRepository

    log = get_run_logger()

    http = HttpxAdapter()
    base_url = model.marketplace_url.rstrip("/")

    # schema_files: list of (relative_path, content) where relative_path is relative to schemas/
    schema_files: list[tuple[str, str]] = []

    # Download individual schemas into schemas/
    for schema_ref in model.schema_ids:
        namespace, name = schema_ref.split("/", 1)
        url = f"{base_url}/api/v1/schemas/{namespace}/{name}/download"
        log.info("Downloading schema: %s/%s", namespace, name)

        response = await http.get(url=url, headers={"Accept": "application/x-yaml"})
        content = response.text
        schema_files.append((f"{name}.yml", content))
        log.info("Downloaded %s/%s -> schemas/%s.yml", namespace, name, name)

    # Download collections into schemas/{collection_name}/
    for collection_ref in model.collection_ids:
        namespace, name = collection_ref.split("/", 1)
        url = f"{base_url}/api/v1/collections/{namespace}/{name}/download"
        log.info("Downloading collection: %s/%s", namespace, name)

        response = await http.get(url=url, headers={"Accept": "application/json"})
        data = response.json()
        schemas = data.get("schemas", [])
        for schema in schemas:
            relative_path = f"{name}/{schema['name']}.yml"
            schema_files.append((relative_path, schema["content"]))
            log.info("Downloaded %s/%s from collection -> schemas/%s", schema["namespace"], schema["name"], relative_path)

        skipped = data.get("collection", {}).get("skipped", [])
        for item in skipped:
            log.warning("Skipped %s/%s: %s", item["namespace"], item["name"], item["reason"])

    if not schema_files:
        log.warning("No schema files to install")
        return

    # Get the repository via the SDK client and initialize the local git repo
    client = get_client()
    repo_node = await client.get(kind="CoreRepository", id=model.repository_id)
    repo_name = repo_node.name.value  # type: ignore[union-attr]

    log.info("Initializing repository %s", repo_name)
    repo = await InfrahubRepository.init(
        id=model.repository_id,
        name=repo_name,
        client=client,
    )

    branch_name = model.branch_name
    git_repo = repo.get_git_repo_worktree(identifier=branch_name)
    worktree = repo.get_worktree(identifier=branch_name)
    worktree_path = Path(worktree.directory)

    # Write schema files into schemas/ directory (collections go into schemas/{collection_name}/)
    schemas_dir = worktree_path / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)

    files_to_add: list[str] = []
    for relative_path, content_str in schema_files:
        file_path = schemas_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content_str, encoding="utf-8")
        files_to_add.append(str(file_path))
        log.info("Wrote schema file: schemas/%s", relative_path)

    # Create .infrahub.yml if it doesn't already exist
    infrahub_yml_path = worktree_path / ".infrahub.yml"
    if not infrahub_yml_path.exists():
        infrahub_yml_path.write_text("---\nschemas:\n  - schemas\n", encoding="utf-8")
        files_to_add.append(str(infrahub_yml_path))
        log.info("Created .infrahub.yml")

    # Stage, commit, and push
    git_repo.index.add(files_to_add)
    commit = git_repo.index.commit(
        f"Add {len(schema_files)} marketplace schema(s)\n\nInstalled via Infrahub Configuration Wizard"
    )

    new_commit = str(commit)
    log.info("Committed %d schema files as %s", len(schema_files), new_commit)

    # Push to remote — the graph commit will update automatically on next sync
    pushed = await repo.push(branch_name=branch_name)
    if pushed:
        log.info("Pushed to remote origin for branch %s", branch_name)
    else:
        log.warning("Repository has no remote origin, skipping push")

    log.info("Marketplace schema installation completed successfully")
