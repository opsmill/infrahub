from infrahub.core.branch import Branch


async def test_node_standard_create(session):

    branch1 = Branch(name="branch1", status="OPEN", description="Second Branch", is_default=False, is_data_only=True)
    await branch1.save(session=session)

    assert branch1.id is not None
