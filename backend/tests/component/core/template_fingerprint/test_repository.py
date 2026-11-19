from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.initialization import create_branch
from infrahub.core.template_fingerprint.models import FingerprintKey, RecordedFingerprint, TemplateFamily
from infrahub.core.template_fingerprint.repository import TemplateFingerprintRepository
from tests.helpers.db_query_counter import CountingInfrahubDatabase

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

LABEL = TemplateFamily.DISPLAY_LABEL_JINJA2
HFID = TemplateFamily.HUMAN_FRIENDLY_ID


def _record(family: TemplateFamily, branch: str, kind: str, fingerprint: str) -> RecordedFingerprint:
    return RecordedFingerprint(key=FingerprintKey(family=family, branch=branch, kind=kind), fingerprint=fingerprint)


async def _count_vertices(db: InfrahubDatabase) -> int:
    results = await db.execute_query(query="MATCH (f:TemplateFingerprint) RETURN count(f) AS total")
    return results[0]["total"]


async def test_get_by_family_returns_only_that_family(db: InfrahubDatabase, default_branch: Branch) -> None:
    repository = TemplateFingerprintRepository(db=db)
    await repository.upsert(
        [_record(LABEL, "main", "TestCar", "h1"), _record(HFID, "main", "TestCar", "h2")],
    )

    assert await repository.get_by_family(LABEL) == [_record(LABEL, "main", "TestCar", "h1")]
    assert await repository.get_by_family(HFID) == [_record(HFID, "main", "TestCar", "h2")]


async def test_upsert_creates_then_overwrites_one_vertex_per_key(db: InfrahubDatabase, default_branch: Branch) -> None:
    repository = TemplateFingerprintRepository(db=db)

    await repository.upsert([_record(LABEL, "main", "TestCar", "h1")])
    await repository.upsert([_record(LABEL, "main", "TestCar", "h2")])

    assert await repository.get_by_family(LABEL) == [_record(LABEL, "main", "TestCar", "h2")]
    assert await _count_vertices(db) == 1


async def test_writes_skip_branch_without_branch_vertex(db: InfrahubDatabase, default_branch: Branch) -> None:
    repository = TemplateFingerprintRepository(db=db)

    await repository.upsert([_record(LABEL, "deleted", "TestCar", "h1")])
    created = await repository.insert_missing([_record(LABEL, "deleted", "TestPerson", "h1")])

    assert created == 0
    assert await _count_vertices(db) == 0


async def test_insert_missing_creates_only_missing_records(db: InfrahubDatabase, default_branch: Branch) -> None:
    await create_branch(branch_name="branch1", db=db)
    repository = TemplateFingerprintRepository(db=db)
    await repository.upsert([_record(LABEL, "main", "TestCar", "h-existing")])

    created = await repository.insert_missing(
        [
            _record(LABEL, "main", "TestCar", "h-new"),
            _record(LABEL, "main", "TestPerson", "h2"),
            _record(LABEL, "branch1", "TestCar", "h3"),
        ]
    )

    assert created == 2
    assert await repository.get_by_family(LABEL) == [
        _record(LABEL, "branch1", "TestCar", "h3"),
        _record(LABEL, "main", "TestCar", "h-existing"),
        _record(LABEL, "main", "TestPerson", "h2"),
    ]
    assert await repository.insert_missing([_record(LABEL, "main", "TestPerson", "h-other")]) == 0


async def test_delete_removes_only_listed_keys(db: InfrahubDatabase, default_branch: Branch) -> None:
    repository = TemplateFingerprintRepository(db=db)
    await repository.upsert(
        [
            _record(LABEL, "main", "TestCar", "h1"),
            _record(LABEL, "main", "TestPerson", "h2"),
            _record(HFID, "main", "TestCar", "h3"),
        ]
    )

    await repository.delete([FingerprintKey(family=LABEL, branch="main", kind="TestCar")])

    assert await repository.get_by_family(LABEL) == [_record(LABEL, "main", "TestPerson", "h2")]
    assert await repository.get_by_family(HFID) == [_record(HFID, "main", "TestCar", "h3")]


async def test_delete_branch_removes_only_that_branch(db: InfrahubDatabase, default_branch: Branch) -> None:
    await create_branch(branch_name="branch1", db=db)
    repository = TemplateFingerprintRepository(db=db)
    await repository.upsert(
        [
            _record(LABEL, "main", "TestCar", "h1"),
            _record(LABEL, "branch1", "TestCar", "h2"),
            _record(HFID, "branch1", "TestCar", "h3"),
        ]
    )

    await repository.delete_branch("branch1")

    assert await repository.get_by_family(LABEL) == [_record(LABEL, "main", "TestCar", "h1")]
    assert await repository.get_by_family(HFID) == []


async def test_writes_on_empty_list_send_no_query(db: InfrahubDatabase, default_branch: Branch) -> None:
    counting_db = CountingInfrahubDatabase.from_db(db=db)
    repository = TemplateFingerprintRepository(db=counting_db)

    await repository.upsert([])
    created = await repository.insert_missing([])
    await repository.delete([])

    assert created == 0
    assert sum(counting_db.query_counts.values()) == 0
