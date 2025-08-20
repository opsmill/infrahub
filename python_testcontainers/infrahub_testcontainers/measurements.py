from .models import ContextUnit, MeasurementDefinition

NODE_QUERY_TIME = MeasurementDefinition(
    name="node_query",
    description="Query some nodes",
    dimensions=["kind"],
    unit=ContextUnit.TIME,
)

NODE_CREATE_TIME = MeasurementDefinition(
    name="node_mutation_create",
    description="Create a new node",
    dimensions=["kind"],
    unit=ContextUnit.TIME,
)

NODE_UPDATE_TIME = MeasurementDefinition(
    name="node_mutation_update",
    description="Update an existing node",
    dimensions=["kind"],
    unit=ContextUnit.TIME,
)

NODE_DELETE_TIME = MeasurementDefinition(
    name="node_mutation_delete",
    description="Delete a node",
    dimensions=["kind"],
    unit=ContextUnit.TIME,
)

SCHEMA_INITIAL_LOAD_TIME = MeasurementDefinition(
    name="schema_initial_load",
    description="Load the initial schema",
    dimensions=["branch"],
    unit=ContextUnit.TIME,
)

SCHEMA_UPDATE_TIME = MeasurementDefinition(
    name="schema_update",
    description="Update the schema",
    dimensions=["branch"],
    unit=ContextUnit.TIME,
)

DATABASE_SIZE = MeasurementDefinition(
    name="database_size",
    description="Size of the database",
    unit=ContextUnit.DISK,
)

DIFF_CREATE_TIME = MeasurementDefinition(
    name="diff_create",
    description="Create a new diff",
    unit=ContextUnit.TIME,
)

DIFF_APPLY_TIME = MeasurementDefinition(
    name="diff_update",
    description="Update an existing diff",
    unit=ContextUnit.TIME,
)

BRANCH_CREATE_TIME = MeasurementDefinition(
    name="branch_create",
    description="Create a new branch",
    unit=ContextUnit.TIME,
)

BRANCH_MERGE_TIME = MeasurementDefinition(
    name="branch_merge",
    description="Merge a branch",
    unit=ContextUnit.TIME,
)

BRANCH_REBASE_TIME = MeasurementDefinition(
    name="branch_rebase",
    description="Rebase a branch",
    unit=ContextUnit.TIME,
)

SCRIPT_EXECUTION_TIME = MeasurementDefinition(
    name="script_execution",
    description="Execute a script",
    dimensions=["name"],
    unit=ContextUnit.TIME,
)

GENERATOR_EXECUTION_TIME = MeasurementDefinition(
    name="generator_execution",
    description="Execute a generator",
    dimensions=["name"],
    unit=ContextUnit.TIME,
)
