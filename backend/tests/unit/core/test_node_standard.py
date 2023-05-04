from neo4j import AsyncSession

from infrahub.core.branch import Branch


async def test_node_standard_create(session: AsyncSession, empty_database):
    branch1 = Branch(
        name="branch1",
        status="OPEN",
        description="Second Branch",
        is_default=False,
        is_data_only=True,
        schema_hash=None,
    )
    await branch1.save(session=session)

    assert branch1.id is not None


async def test_get(session: AsyncSession, empty_database):
    branch1 = Branch(name="branch1", status="OPEN", description="Second Branch", is_default=False, is_data_only=True)
    assert await branch1.save(session=session)

    branch11 = await Branch.get(id=branch1.uuid, session=session)
    assert branch11.dict(exclude={"uuid"}) == branch1.dict(exclude={"uuid"})
    assert str(branch11.uuid) == str(branch1.uuid)
