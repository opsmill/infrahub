
import uuid
from infrahub.git import GitRepository

async def test_new(git_upstream_repo_01):

    repo = await GitRepository.new(id=uuid.uuid4(), branch_name="main", name="infrahub-test-fixture-01", location=f"file:/{git_upstream_repo_01}")
    assert True