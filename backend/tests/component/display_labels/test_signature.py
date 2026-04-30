from infrahub.database import InfrahubDatabase
from infrahub.display_labels.signature import DisplayLabelSignature
from infrahub.hfid.signature import HFIDSignature


async def test_create(db: InfrahubDatabase, empty_database: None) -> None:
    sig = DisplayLabelSignature(branch="main", target_kind="TestCar", definition_hash="abc123")
    await sig.save(db=db)

    assert sig.id is not None
    assert sig.uuid is not None


async def test_get(db: InfrahubDatabase, empty_database: None) -> None:
    sig = DisplayLabelSignature(branch="main", target_kind="TestCar", definition_hash="abc123")
    await sig.save(db=db)

    fetched = await DisplayLabelSignature.get(id=str(sig.uuid), db=db)
    assert fetched is not None
    assert fetched.branch == "main"
    assert fetched.target_kind == "TestCar"
    assert fetched.definition_hash == "abc123"


async def test_update(db: InfrahubDatabase, empty_database: None) -> None:
    sig = DisplayLabelSignature(branch="main", target_kind="TestCar", definition_hash="abc123")
    await sig.save(db=db)

    sig.definition_hash = "def456"
    await sig.save(db=db)

    fetched = await DisplayLabelSignature.get(id=str(sig.uuid), db=db)
    assert fetched is not None
    assert fetched.definition_hash == "def456"


async def test_delete(db: InfrahubDatabase, empty_database: None) -> None:
    sig = DisplayLabelSignature(branch="main", target_kind="TestCar", definition_hash="abc123")
    await sig.save(db=db)
    other = DisplayLabelSignature(branch="main", target_kind="TestPerson", definition_hash="xyz789")
    await other.save(db=db)

    await sig.delete(db=db)

    remaining = await DisplayLabelSignature.get_list(db=db)
    assert len(remaining) == 1
    assert remaining[0].target_kind == "TestPerson"


async def test_list_unfiltered(db: InfrahubDatabase, empty_database: None) -> None:
    await DisplayLabelSignature(branch="main", target_kind="TestCar", definition_hash="h1").save(db=db)
    await DisplayLabelSignature(branch="main", target_kind="TestPerson", definition_hash="h2").save(db=db)
    await DisplayLabelSignature(branch="dev", target_kind="TestCar", definition_hash="h3").save(db=db)

    sigs = await DisplayLabelSignature.get_list(db=db)
    assert len(sigs) == 3


async def test_list_filter_by_branch(db: InfrahubDatabase, empty_database: None) -> None:
    await DisplayLabelSignature(branch="main", target_kind="TestCar", definition_hash="h1").save(db=db)
    await DisplayLabelSignature(branch="main", target_kind="TestPerson", definition_hash="h2").save(db=db)
    await DisplayLabelSignature(branch="dev", target_kind="TestCar", definition_hash="h3").save(db=db)

    main_sigs = await DisplayLabelSignature.get_list(db=db, branch="main")
    assert len(main_sigs) == 2
    assert {sig.target_kind for sig in main_sigs} == {"TestCar", "TestPerson"}

    dev_sigs = await DisplayLabelSignature.get_list(db=db, branch="dev")
    assert len(dev_sigs) == 1
    assert dev_sigs[0].target_kind == "TestCar"


async def test_list_filter_by_branch_and_target_kind(db: InfrahubDatabase, empty_database: None) -> None:
    await DisplayLabelSignature(branch="main", target_kind="TestCar", definition_hash="h1").save(db=db)
    await DisplayLabelSignature(branch="main", target_kind="TestPerson", definition_hash="h2").save(db=db)
    await DisplayLabelSignature(branch="dev", target_kind="TestCar", definition_hash="h3").save(db=db)

    matched = await DisplayLabelSignature.get_list(db=db, branch="main", target_kind="TestCar")
    assert len(matched) == 1
    assert matched[0].definition_hash == "h1"

    no_match = await DisplayLabelSignature.get_list(db=db, branch="main", target_kind="Unknown")
    assert no_match == []


async def test_label_isolation_from_other_signature_kinds(db: InfrahubDatabase, empty_database: None) -> None:
    await DisplayLabelSignature(branch="main", target_kind="TestCar", definition_hash="display_hash").save(db=db)
    await HFIDSignature(branch="main", target_kind="TestCar", definition_hash="hfid_hash_value").save(db=db)

    display_sigs = await DisplayLabelSignature.get_list(db=db)
    hfid_sigs = await HFIDSignature.get_list(db=db)

    assert len(display_sigs) == 1
    assert len(hfid_sigs) == 1
    assert display_sigs[0].definition_hash == "display_hash"
    assert hfid_sigs[0].definition_hash == "hfid_hash_value"
