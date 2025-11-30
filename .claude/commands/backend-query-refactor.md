# Refactor Query Command

Refactor the specified Query class to add a Pydantic data class representing the query's returned data.

## Input

Query name or file path: $ARGUMENTS

## Instructions

### Step 1: Locate the Query

1. If a file path is provided, read that file directly
2. If a query name is provided (e.g., `GetProfileDataQuery`), search for it in:
   - `backend/infrahub/core/query/`
   - `backend/infrahub/` (recursive)
   - Other relevant directories

### Step 2: Analyze Query Usage

1. Find all places where the query is instantiated and executed
2. Identify how `self.results` is consumed:
   - Look for `for result in self.results:` patterns
   - Look for `self.get_result()` calls
   - Look for methods that process results (e.g., `get_*` methods)
3. Document all fields being extracted from results using:
   - `result.get(label="...")`
   - `result.get_as_type(label="...", return_type=...)`
   - `result.get_as_str(label="...")`
   - `result.get_node(label="...")`
   - `result.get_rel(label="...")`
4. Find all callers of the query and identify what data they actually use from the results

### Step 3: Analyze Query Purpose

1. Read the query's Cypher code and comments to understand what it does
2. Review the `query_init` method to understand the query's purpose
3. Check for any existing docstrings or comments that describe the query
4. Based on this analysis, write a clear, concise description of:
   - What the query retrieves or accomplishes
   - When/why this query is used
   - Any important context about the data it returns

### Step 4: Design the Pydantic Data Class

Based on the analysis, create a Pydantic class that:

1. **Name**: Use the query class name + `Data` suffix
   - Example: `GetProfileDataQuery` -> `GetProfileDataQueryData`
   - If the query name ends with `Query`, the data class is `{QueryName}Data`

2. **Fields**: Include only the data points that are actually used by callers
   - Extract flat values, not entire Neo4j nodes or relationships
   - Use appropriate Python types (str, int, bool, etc.)
   - Use `T | None` for nullable fields
   - Use `list[T]` for collection fields
   - **Use `Field(description="...")` for every field** to document its purpose

3. **Avoid returning**:
   - Entire Neo4j `Node` objects
   - Entire Neo4j `Relationship` objects
   - Raw `QueryResult` objects
   - Unnecessary nested structures

4. **Convert existing `@dataclass` to Pydantic**: If the query already uses a `@dataclass` to return structured data, convert it to a Pydantic `BaseModel` for consistency and better features:

   **Why convert:**
   - Pydantic provides better validation, serialization, and documentation
   - `model_construct()` allows skipping validation for performance
   - Consistent pattern across all queries
   - Better IDE support and type inference

   **Conversion example:**
   ```python
   # Before: dataclass
   @dataclass
   class RelationshipPeersData:
       id: UUID
       identifier: str
       source_id: UUID

   # After: Pydantic
   class RelationshipPeersData(BaseModel):
       id: UUID = Field(description="The UUID of the relationship")
       identifier: str = Field(description="The relationship identifier/name")
       source_id: UUID = Field(description="The UUID of the source node")
   ```

   **Migration steps:**
   1. Remove the `@dataclass` decorator
   2. Add `BaseModel` as parent class
   3. Add `Field(description="...")` to each field
   4. Update any direct instantiation to use `model_construct()` for performance
   5. Keep the same class name to avoid breaking callers
   6. Remove the `@dataclass` import if no longer needed in the file

### Step 5: Implement the Pydantic Class

Add the Pydantic class to the **same file** as the query, placing it **before** the Query class definition.

```python
from pydantic import BaseModel, Field

class {QueryName}Data(BaseModel):
    """Data returned by {QueryName}.

    {Detailed description of what this data represents and when it's used.}
    """

    field_name: str = Field(description="Description of what field_name represents")
    other_field: int = Field(description="Description of what other_field represents")
    optional_field: str | None = Field(default=None, description="Description of optional_field")
```

### Step 6: Add Query Class Documentation

If the Query class lacks a docstring, add one that describes:
- What the query does
- What data it retrieves from the database
- Any important parameters or configuration

```python
class {QueryName}(Query):
    """Query to retrieve {description of what is retrieved}.

    This query is used to {explain the purpose and when it's used}.

    Args:
        {parameter}: {description of parameter}

    Returns:
        Results containing {brief description of returned data}.
    """
```

### Step 7: Optimize the Query RETURN Clause

**Important**: Refactor the Cypher query to return only the specific values needed, not entire nodes or relationships. This reduces data transfer from Neo4j and simplifies result processing.

**Before** (inefficient - returns entire nodes):
```python
self.return_labels = ["n", "r", "av"]
# Then in get_data(): result.get_node("n").get("uuid")
```

**After** (efficient - returns only needed values):
```python
self.return_labels = ["n.uuid AS node_uuid", "n.kind AS node_kind", "r.from AS updated_at"]
# Then in get_data(): result.get("node_uuid")
```

When refactoring:
1. Identify all properties actually used from each node/relationship
2. Update `self.return_labels` to return `alias.property AS label_name` for each value
3. Use descriptive label names that match your Pydantic data class field names
4. For relationship element IDs, use `elementId(r) AS relationship_id`

**Example transformation**:
```python
# Before:
self.return_labels = ["a", "av", "r"]
# Usage: result.get_node("a").get("uuid"), result.get_rel("r").get("branch")

# After:
self.return_labels = [
    "a.uuid AS attribute_uuid",
    "av.uuid AS attribute_value_uuid",
    "elementId(r) AS relationship_id",
    "r.branch AS branch",
]
# Usage: result.get("attribute_uuid"), result.get("branch")
```

### Step 8: Add a Method to Return Typed Data

If the query doesn't already have a method that returns structured data, add one.

**Important**: Use `model_construct()` instead of the normal constructor to skip validation for better performance. Since we control the query results and know the data format is correct, validation is unnecessary overhead.

```python
def get_data(self) -> list[{QueryName}Data]:
    """Return query results as typed data objects."""
    return [
        {QueryName}Data.model_construct(
            field_name=result.get("field_name"),
            other_field=result.get("other_field"),
            optional_field=result.get("optional_field"),
        )
        for result in self.results
    ]
```

### Step 9: Analyze Performance Best Practices

Review the query for performance issues and memory consumption:

**Cypher Query Performance Checklist:**
1. **Index usage**: Does the query start with indexed properties (uuid, name)?
2. **Early filtering**: Are WHERE clauses applied as early as possible?
3. **LIMIT placement**: Is LIMIT used inside subqueries to prevent unbounded results?
4. **Cartesian products**: Are there unintended cartesian products from multiple MATCH clauses?
5. **Variable-length paths**: Are `*` or `*..n` patterns bounded appropriately?
6. **OPTIONAL MATCH**: Could expensive OPTIONAL MATCH be avoided or optimized?

**Python/Memory Performance Checklist:**
1. **Generator vs List**: Use `Generator` (yield) instead of building lists for large result sets
2. **Lazy iteration**: Use `get_results()` generator instead of `self.results` list when possible
3. **Avoid intermediate lists**: Don't create temporary lists when iterating
4. **Early termination**: Can the query use LIMIT or should callers use itertools.islice?

**Anti-patterns to flag:**
```python
# Bad: Building full list in memory
def get_data(self) -> list[Data]:
    return [Data(...) for result in self.results]

# Good: Generator for large result sets
def get_data(self) -> Generator[Data, None, None]:
    for result in self.get_results():
        yield Data(...)

# Bad: Multiple iterations over results
for r in self.results:  # First iteration
    ...
for r in self.results:  # Second iteration - results already consumed or re-fetched
    ...

# Bad: Storing entire nodes when only a few properties needed
self.return_labels = ["n", "r"]  # Returns all properties

# Good: Return only needed properties
self.return_labels = ["n.uuid AS id", "n.kind AS kind"]
```

### Step 10: Check for Existing Tests

Search for existing tests for this query:

1. Search in `backend/tests/unit/core/query/` for unit tests
2. Search in `backend/tests/` for any test file mentioning the query class name
3. Check if there are performance/benchmark tests

Report findings:
- List any existing test files and what they cover
- Identify gaps in test coverage
- Note if performance tests exist

### Step 11: Propose Tests (if needed)

If tests are missing or incomplete, propose:

**Unit Tests** (in `backend/tests/unit/core/query/test_{module}.py`):
```python
import pytest
from infrahub.core.query.{module} import {QueryName}, {QueryName}Data

class Test{QueryName}:
    async def test_query_returns_expected_fields(self, db, default_branch):
        """Test that query returns all expected fields."""
        # Setup test data
        ...

        query = await {QueryName}.init(db=db, branch=default_branch, ...)
        await query.execute(db=db)

        results = list(query.get_data())
        assert len(results) == expected_count
        assert results[0].field_name == expected_value

    async def test_query_handles_empty_results(self, db, default_branch):
        """Test query behavior with no matching data."""
        query = await {QueryName}.init(db=db, branch=default_branch, ...)
        await query.execute(db=db)

        results = list(query.get_data())
        assert results == []

    async def test_query_filters_correctly(self, db, default_branch):
        """Test that query filters work as expected."""
        ...
```

**Performance Tests** (if query is performance-critical):
```python
import pytest
from infrahub.core.query.{module} import {QueryName}

class Test{QueryName}Performance:
    @pytest.mark.performance
    async def test_query_scales_linearly(self, db, default_branch, benchmark):
        """Test query performance scales acceptably with data size."""
        # Create test data of known size
        ...

        async def run_query():
            query = await {QueryName}.init(db=db, branch=default_branch, ...)
            await query.execute(db=db)
            return list(query.get_data())

        result = benchmark(run_query)
        assert len(result) == expected_count

    @pytest.mark.performance
    async def test_memory_usage_acceptable(self, db, default_branch):
        """Test query doesn't consume excessive memory."""
        import tracemalloc
        tracemalloc.start()

        query = await {QueryName}.init(db=db, branch=default_branch, ...)
        await query.execute(db=db)
        # Use generator to avoid holding all results
        count = sum(1 for _ in query.get_data())

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Assert peak memory is within acceptable bounds
        assert peak < MAX_ACCEPTABLE_BYTES
```

### Step 12: Update Callers (if requested)

If the user requests it, update the callers to use the new typed data class instead of raw results.

## Output

1. Show the analysis of how the query is used
2. Show the proposed Pydantic data class with field descriptions
3. Show the updated query file with:
   - The new Pydantic data class
   - Updated Query class docstring
   - The `get_data()` method
4. List any callers that could be updated to use the new typed data
5. **Performance Analysis**:
   - Cypher query performance issues found
   - Memory/Python performance issues found
   - Recommendations for improvement
6. **Test Coverage**:
   - List existing tests found
   - Gaps in coverage
   - Proposed new tests (provide complete test code)

## Example

For a query like:

```python
class GetNodeByIdQuery(Query):
    async def query_init(self, db: InfrahubDatabase, **kwargs) -> None:
        query = """
        MATCH (n:Node { uuid: $node_id })-[r:IS_PART_OF]->(:Root)
        """
        self.add_to_query(query)
        # Before: returning entire nodes
        # self.return_labels = ["n", "r"]

        # After: returning only needed values
        self.return_labels = [
            "n.uuid AS node_uuid",
            "n.kind AS node_kind",
            "r.from AS updated_at",
        ]
```

The refactored version would include:

```python
from pydantic import BaseModel, Field

class GetNodeByIdQueryData(BaseModel):
    """Data returned by GetNodeByIdQuery.

    Represents a node retrieved from the database by its unique identifier,
    including its kind and last modification timestamp.
    """

    node_uuid: str = Field(description="The unique identifier (UUID) of the node")
    node_kind: str = Field(description="The schema kind/type of the node (e.g., 'InfraDevice')")
    updated_at: str = Field(description="ISO timestamp of when the node was last updated")


class GetNodeByIdQuery(Query):
    """Query to retrieve a node by its unique identifier.

    This query fetches a single node from the database using its UUID,
    returning its kind and last update timestamp.

    Args:
        node_id: The UUID of the node to retrieve.
        branch: The branch to query against.

    Returns:
        Results containing the node's UUID, kind, and update timestamp.
    """

    # ... existing code ...

    def get_data(self) -> list[GetNodeByIdQueryData]:
        """Return query results as typed data objects."""
        return [
            GetNodeByIdQueryData.model_construct(
                node_uuid=result.get("node_uuid"),
                node_kind=result.get("node_kind"),
                updated_at=result.get("updated_at"),
            )
            for result in self.results
        ]
```

### Performance Analysis Example

**Cypher Performance:**
- ✅ Query starts with indexed property lookup (`uuid`)
- ✅ LIMIT is used appropriately
- ⚠️ Consider adding index on `kind` if frequently filtered

**Memory Performance:**
- ⚠️ `get_data()` returns a list - consider using a generator for large result sets:
```python
def get_data(self) -> Generator[GetNodeByIdQueryData, None, None]:
    for result in self.get_results():
        yield GetNodeByIdQueryData.model_construct(...)
```

### Test Example

```python
# backend/tests/unit/core/query/test_node.py
import pytest
from infrahub.core.query.node import GetNodeByIdQuery, GetNodeByIdQueryData

class TestGetNodeByIdQuery:
    async def test_returns_node_data(self, db, default_branch, car_person_schema):
        """Test query returns correct node data."""
        # Create a test node
        from infrahub.core.node import Node
        node = await Node.init(db=db, branch=default_branch, schema="TestPerson")
        await node.new(db=db, name="John")
        await node.save(db=db)

        # Execute query
        query = await GetNodeByIdQuery.init(
            db=db, branch=default_branch, node_id=node.id
        )
        await query.execute(db=db)

        # Verify results
        results = list(query.get_data())
        assert len(results) == 1
        assert results[0].node_uuid == node.id
        assert results[0].node_kind == "TestPerson"

    async def test_empty_results_for_nonexistent_node(self, db, default_branch):
        """Test query returns empty for non-existent node."""
        query = await GetNodeByIdQuery.init(
            db=db, branch=default_branch, node_id="non-existent-uuid"
        )
        await query.execute(db=db)

        results = list(query.get_data())
        assert results == []
```
