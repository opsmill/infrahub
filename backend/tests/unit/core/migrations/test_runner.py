from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.branch.models import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.core.initialization import create_branch
from infrahub.core.migrations.runner import MigrationRunner

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


def test_instantiation(default_branch: Branch) -> None:
    assert MigrationRunner(branch=Branch(name="foo"))

    with pytest.raises(ValueError):
        MigrationRunner(branch=default_branch)

    with pytest.raises(ValueError):
        MigrationRunner(branch=Branch(name=GLOBAL_BRANCH_NAME))


async def test_has_migrations(default_branch: Branch, db: InfrahubDatabase) -> None:
    branch = await create_branch(db=db, branch_name="foo")

    runner = MigrationRunner(branch=branch)
    assert not runner.has_migrations()

    branch.graph_version = None
    runner = MigrationRunner(branch=branch)
    await branch.save(db=db)
    assert runner.has_migrations()

    branch.graph_version = 40
    runner = MigrationRunner(branch=branch)
    await branch.save(db=db)
    assert runner.has_migrations()


async def test_applicable_migrations(default_branch: Branch, db: InfrahubDatabase) -> None:
    branch = await create_branch(db=db, branch_name="foo")

    runner = MigrationRunner(branch=branch)
    assert not runner.applicable_migrations

    branch.graph_version = None
    runner = MigrationRunner(branch=branch)
    await branch.save(db=db)
    assert runner.applicable_migrations
    assert [m.name for m in runner.applicable_migrations][0] == "043_backfill_hfid_display_label_in_db"

    branch.graph_version = 40
    runner = MigrationRunner(branch=branch)
    await branch.save(db=db)
    assert runner.applicable_migrations
    assert [m.name for m in runner.applicable_migrations][0] == "043_backfill_hfid_display_label_in_db"
