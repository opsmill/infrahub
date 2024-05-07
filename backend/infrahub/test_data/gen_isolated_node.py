import uuid

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.log import get_logger

from .shared import DataGenerator

log = get_logger()


class GenerateIsolatedNodes(DataGenerator):
    async def load_data(
        self,
        nbr_tags: int = 100,
        nbr_repository: int = 100,
    ):
        """Generate a large number of Tags and Repositories"""
        default_branch = await registry.get_branch(db=self.db)

        if self.progress:
            task_tag = self.progress.add_task("Loading TAG", total=nbr_tags)
            task_repo = self.progress.add_task("Loading REPOSITORY", total=nbr_repository)

        tags = {}
        repository = {}

        tag_schema = registry.schema.get_node_schema(name=InfrahubKind.TAG, branch=default_branch)
        repository_schema = registry.schema.get_node_schema(name=InfrahubKind.REPOSITORY, branch=default_branch)

        # -------------------------------------------------------------------------------------
        # TAG
        # -------------------------------------------------------------------------------------
        batch = self.create_batch()
        for _ in range(nbr_tags):
            short_id = str(uuid.uuid4())[:8]
            tag_name = f"tag-{short_id}"
            obj = await Node.init(db=self.db, schema=tag_schema, branch=default_branch)
            await obj.new(db=self.db, name=tag_name)
            batch.add(task=self.save_obj, obj=obj)
            tags[tag_name] = obj

        async for _ in batch.execute():
            if self.progress:
                self.progress.advance(task_tag)

        # -------------------------------------------------------------------------------------
        # REPOSITORY
        # -------------------------------------------------------------------------------------
        batch = self.create_batch()
        for _ in range(nbr_repository):
            short_id = str(uuid.uuid4())[:8]
            repo_name = f"repository-{short_id}"
            obj = await Node.init(db=self.db, schema=repository_schema, branch=default_branch)
            await obj.new(db=self.db, name=repo_name, location=f"git://{repo_name}")
            batch.add(task=self.save_obj, obj=obj)
            repository[repo_name] = obj

        async for _ in batch.execute():
            if self.progress:
                self.progress.advance(task_repo)
