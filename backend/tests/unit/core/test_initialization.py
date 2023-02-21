from infrahub.core.initialization import first_time_initialization


async def test_first_time_initialization(session, default_branch):
    await first_time_initialization(session=session)
    assert True
