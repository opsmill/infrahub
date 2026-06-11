"""Process-wide cache of fully-processed schema branches for test fixtures.

Loading and processing the internal/core schemas is CPU-expensive (~0.4s per call)
while the inputs never change within a test session. Each schema set is built once
per process and tests receive an isolated duplicate, which is orders of magnitude
cheaper than re-processing the same schemas for every test.
"""

from infrahub.core import registry
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.schema.schema_branch import SchemaBranch

_SCHEMA_SETS: dict[str, tuple[dict, ...]] = {
    "internal": (internal_schema,),
    "internal-core": (internal_schema, core_models),
}
_PROCESSED: dict[str, SchemaBranch] = {}


def _get_processed(key: str) -> SchemaBranch:
    if key not in _PROCESSED:
        manager = SchemaManager()
        for schema in _SCHEMA_SETS[key]:
            manager.register_schema(schema=SchemaRoot(**schema), branch=key)
        _PROCESSED[key] = manager.get_schema_branch(name=key)
    return _PROCESSED[key]


# States from which a branch may be replaced by an installed copy: untouched, or exactly
# the pristine result of an earlier install step of the same chain.
_REPLACEABLE_PRIOR_STATES: dict[str, tuple[str, ...]] = {
    "internal": ("internal",),
    "internal-core": ("internal", "internal-core"),
}


def _branch_is_empty(branch: SchemaBranch) -> bool:
    return not (branch.nodes or branch.generics or branch.profiles or branch.templates)


def _branch_matches(branch: SchemaBranch, key: str) -> bool:
    pristine = _get_processed(key)
    return (
        branch.nodes == pristine.nodes
        and branch.generics == pristine.generics
        and branch.profiles == pristine.profiles
        and branch.templates == pristine.templates
    )


def _install(branch_name: str, key: str) -> SchemaBranch:
    manager = registry.schema
    if manager.has_schema_branch(branch_name):
        existing = manager.get_schema_branch(name=branch_name)
        replaceable = _branch_is_empty(existing) or any(
            _branch_matches(branch=existing, key=prior) for prior in _REPLACEABLE_PRIOR_STATES[key]
        )
        if not replaceable:
            # The branch already diverged (the test registered or customized schemas before
            # this fixture ran). Replacing it would drop those changes and would also give
            # this branch state the same schema hash as every other pristine installation,
            # cross-contaminating hash-keyed caches. Merge the raw schemas the slow way,
            # which preserves the content and the chain-specific hash.
            for schema in _SCHEMA_SETS[key]:
                manager.register_schema(schema=SchemaRoot(**schema), branch=branch_name)
            return manager.get_schema_branch(name=branch_name)
    pristine = _get_processed(key)
    schema_branch = pristine.duplicate(name=branch_name)
    # duplicate() shares the pristine branch's schema cache object; hand each installation
    # its own copy so schemas registered later in a test cannot leak into other tests.
    schema_branch._cache = dict(pristine._cache)
    manager.set_schema_branch(name=branch_name, schema=schema_branch)
    return schema_branch


def install_processed_internal_schema_branch(branch_name: str) -> SchemaBranch:
    """Install a pre-processed copy of the internal schema into the active schema registry."""
    return _install(branch_name=branch_name, key="internal")


def install_processed_core_schema_branch(branch_name: str) -> SchemaBranch:
    """Install a pre-processed copy of the internal + core schemas into the active schema registry."""
    return _install(branch_name=branch_name, key="internal-core")
