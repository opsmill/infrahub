from infrahub.computed_attribute.signature import ComputedAttrJinja2Signature
from infrahub.database import InfrahubDatabase


async def test_create(db: InfrahubDatabase, empty_database: None) -> None:
    sig = ComputedAttrJinja2Signature(
        branch="main", target_kind="TestCar", attribute_name="full_name", definition_hash="abc123"
    )
    await sig.save(db=db)

    assert sig.id is not None
    assert sig.uuid is not None


async def test_get(db: InfrahubDatabase, empty_database: None) -> None:
    sig = ComputedAttrJinja2Signature(
        branch="main", target_kind="TestCar", attribute_name="full_name", definition_hash="abc123"
    )
    await sig.save(db=db)

    fetched = await ComputedAttrJinja2Signature.get(id=str(sig.uuid), db=db)
    assert fetched is not None
    assert fetched.branch == "main"
    assert fetched.target_kind == "TestCar"
    assert fetched.attribute_name == "full_name"
    assert fetched.definition_hash == "abc123"


async def test_update(db: InfrahubDatabase, empty_database: None) -> None:
    sig = ComputedAttrJinja2Signature(
        branch="main", target_kind="TestCar", attribute_name="full_name", definition_hash="abc123"
    )
    await sig.save(db=db)

    sig.definition_hash = "def456"
    await sig.save(db=db)

    fetched = await ComputedAttrJinja2Signature.get(id=str(sig.uuid), db=db)
    assert fetched is not None
    assert fetched.definition_hash == "def456"


async def test_delete(db: InfrahubDatabase, empty_database: None) -> None:
    sig = ComputedAttrJinja2Signature(
        branch="main", target_kind="TestCar", attribute_name="full_name", definition_hash="abc123"
    )
    await sig.save(db=db)
    other = ComputedAttrJinja2Signature(
        branch="main", target_kind="TestCar", attribute_name="display", definition_hash="xyz789"
    )
    await other.save(db=db)

    await sig.delete(db=db)

    remaining = await ComputedAttrJinja2Signature.get_list(db=db)
    assert len(remaining) == 1
    assert remaining[0].attribute_name == "display"


async def test_list_unfiltered(db: InfrahubDatabase, empty_database: None) -> None:
    await ComputedAttrJinja2Signature(
        branch="main", target_kind="TestCar", attribute_name="full_name", definition_hash="h1"
    ).save(db=db)
    await ComputedAttrJinja2Signature(
        branch="main", target_kind="TestCar", attribute_name="display", definition_hash="h2"
    ).save(db=db)
    await ComputedAttrJinja2Signature(
        branch="dev", target_kind="TestCar", attribute_name="full_name", definition_hash="h3"
    ).save(db=db)

    sigs = await ComputedAttrJinja2Signature.get_list(db=db)
    assert len(sigs) == 3


async def test_list_filter_by_branch(db: InfrahubDatabase, empty_database: None) -> None:
    await ComputedAttrJinja2Signature(
        branch="main", target_kind="TestCar", attribute_name="full_name", definition_hash="h1"
    ).save(db=db)
    await ComputedAttrJinja2Signature(
        branch="main", target_kind="TestCar", attribute_name="display", definition_hash="h2"
    ).save(db=db)
    await ComputedAttrJinja2Signature(
        branch="dev", target_kind="TestCar", attribute_name="full_name", definition_hash="h3"
    ).save(db=db)

    main_sigs = await ComputedAttrJinja2Signature.get_list(db=db, branch="main")
    assert len(main_sigs) == 2

    dev_sigs = await ComputedAttrJinja2Signature.get_list(db=db, branch="dev")
    assert len(dev_sigs) == 1


async def test_list_filter_disambiguates_attribute_name(db: InfrahubDatabase, empty_database: None) -> None:
    await ComputedAttrJinja2Signature(
        branch="main", target_kind="TestCar", attribute_name="full_name", definition_hash="h_full"
    ).save(db=db)
    await ComputedAttrJinja2Signature(
        branch="main", target_kind="TestCar", attribute_name="display", definition_hash="h_disp"
    ).save(db=db)

    matched = await ComputedAttrJinja2Signature.get_list(
        db=db, branch="main", target_kind="TestCar", attribute_name="full_name"
    )
    assert len(matched) == 1
    assert matched[0].definition_hash == "h_full"

    matched_other = await ComputedAttrJinja2Signature.get_list(
        db=db, branch="main", target_kind="TestCar", attribute_name="display"
    )
    assert len(matched_other) == 1
    assert matched_other[0].definition_hash == "h_disp"
