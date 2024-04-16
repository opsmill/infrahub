import random
import uuid

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.log import get_logger

from .shared import DataGenerator

log = get_logger()


class ProfileAttribute(DataGenerator):
    async def load_data(
        self,
        nbr_person: int = 100,
    ):
        """Generate a large number of Tags and Repositories"""
        default_branch = await registry.get_branch(db=self.db)

        if self.progress:
            task_person = self.progress.add_task("Loading PERSON", total=nbr_person)

        persons = {}

        person_profile_schema = registry.schema.get(name="ProfileTestPerson", branch=default_branch)
        profile1 = await Node.init(db=self.db, schema=person_profile_schema, branch=default_branch)
        await profile1.new(db=self.db, profile_name="profile1", profile_priority=1000, height=180)
        await profile1.save(db=self.db)
        profile2 = await Node.init(db=self.db, schema=person_profile_schema, branch=default_branch)
        await profile2.new(db=self.db, profile_name="profile2", profile_priority=1200, height=150)
        await profile2.save(db=self.db)

        person_schema = registry.schema.get_node_schema(name="TestPerson", branch=default_branch)
        # -------------------------------------------------------------------------------------
        # TAG
        # -------------------------------------------------------------------------------------
        batch = self.create_batch()
        for _ in range(nbr_person):
            short_id = str(uuid.uuid4())[:8]
            rand_height = random.randrange(200)
            name = f"nbr_person-{short_id}"
            obj = await Node.init(db=self.db, schema=person_schema, branch=default_branch)

            profile = profile2
            if rand_height % 2 == 0:
                profile = profile1

            await obj.new(db=self.db, name=name, profiles=[profile])
            batch.add(task=self.save_obj, obj=obj)
            persons[name] = obj

        async for _ in batch.execute():
            if self.progress:
                self.progress.advance(task_person)

        # # -------------------------------------------------------------------------------------
        # # REPOSITORY
        # # -------------------------------------------------------------------------------------
        # batch = self.create_batch()
        # for _ in range(nbr_repository):
        #     short_id = str(uuid.uuid4())[:8]
        #     repo_name = f"repository-{short_id}"
        #     obj = await Node.init(db=self.db, schema=repository_schema, branch=default_branch)
        #     await obj.new(db=self.db, name=repo_name, location=f"git://{repo_name}")
        #     batch.add(task=self.save_obj, obj=obj)
        #     repository[repo_name] = obj

        # async for _ in batch.execute():
        #     if self.progress:
        #         self.progress.advance(task_repo)
