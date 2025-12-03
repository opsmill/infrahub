# ADR-0008: Data Models - Pydantic vs Dataclasses

## Status

Draft

## Context

Infrahub needs robust data validation, serialization, and type safety across API boundaries, database operations, and internal data structures. The system handles complex nested data structures that must be validated and transformed. However, we also need to balance performance and memory efficiency for internal operations that process large volumes of data, especially in the OGM (Object Graph Mapping) layer where we create many instances from database results.

## Performance Analysis

Research and benchmarking revealed significant performance differences between dataclasses and Pydantic:

- **`@dataclass(slots=True)`** is **1.5x faster** for instance creation and uses **22% less memory** compared to regular dataclasses
- **Pydantic v2** is **4-5x slower** for instance creation and uses **2.6x more memory** compared to slotted dataclasses
- `model_construct()` in Pydantic v2 performs similarly to normal Pydantic initialization (not faster as initially assumed)
- **Python 3.13+** provides significant performance improvements for dataclasses

Given these findings, we prioritize performance for internal data structures while maintaining validation at API boundaries.

## Decision

We use a **hybrid approach** with two distinct data modeling strategies:

1. **Pydantic models** for all external-facing data that requires validation, documentation, and FastAPI integration
2. **`@dataclass(slots=True)`** for internal, performance-critical data structures, especially in the OGM layer

### Key Principles

- **Trust database data**: Data retrieved from the database is trusted and does not require re-validation internally
- **No validation overhead internally**: Internal data structures skip validation since data is already validated at API boundaries or trusted from the database
- **Move away from dict structures**: Replace `dict[str, dict[str, str]]` patterns with properly typed dataclass objects
- **Target Python 3.13+**: Directly target Python 3.13+ to benefit from improved dataclass performance rather than supporting both 3.12 and 3.13

### Pydantic Models (External-Facing)

Pydantic is used for all data that crosses external boundaries or needs automatic validation and documentation:

- **REST API models** (`infrahub/api/*`): All request/response models for FastAPI endpoints
  - Examples: `QueryPayload`, `ArtifactGeneratePayload`, `SchemaUpdate`, `ConfigAPI`, `InfoAPI`
  - Benefits: Automatic OpenAPI/Swagger documentation generation, request validation, clear API contracts

- **GraphQL response models**: Models used to serialize data for GraphQL responses
  - Example: `StandardNode` (`infrahub/core/node/standard.py`)

- **Events** (`infrahub/events/models.py`): External event structures
  - Example: `InfrahubEvent`, `EventMeta`

- **Message Bus messages** (`infrahub/message_bus/*`): Currently using Pydantic for all message types
  - Examples: `InfrahubMessage`, `RefreshGitFetch`, `BaseProposedChangeWithDiffMessage`
  - **Note**: Internal message bus messages may migrate to dataclasses in the future for performance, but external-facing message contracts will remain Pydantic

- **Transform and Artifact models**: External API models for transformations and artifacts
  - Examples: `TransformPythonData`, `TransformJinjaTemplateData`, `CheckArtifactCreate`

- **Settings and Configuration**: Using Pydantic Settings for application configuration

### Slotted Dataclasses (Internal, Performance-Focused)

**`@dataclass(slots=True)`** is used for internal data structures where performance and memory efficiency are priorities. This is especially important in the OGM layer where many instances are created from database query results.

- **OGM Layer** (`infrahub/core/node/*`, `infrahub/core/relationship/*`): Object Graph Mapping structures representing database entities
  - Node and relationship data structures
  - Internal attribute and relationship representations

- **Database Query Results** (`infrahub/core/query/*`):
  - `QueryStat`: Query execution statistics
  - `RelData`: Relationship data from database queries
  - `FlagPropertyData`, `NodePropertyData`: Relationship property data
  - `RelationshipPeerData`, `RelationshipPeersData`: Relationship peer information
  - `FullRelationshipIdentifier`: Relationship identifier structures

- **Profile Data** (`infrahub/profiles/queries/get_profile_data.py`):
  - `ProfileData`: Internal profile attribute values

- **IPAM Models** (`infrahub/core/ipam/model.py`):
  - `IpamNodeDetails`: IP address management node details

- **GraphQL Loaders** (`infrahub/graphql/loaders/node.py`):
  - `GetManyParams`: Parameters for batch loading nodes

- **Diff and Changelog** (`infrahub/core/diff/*`):
  - `DisplayLabelRequest`: Request for display label enrichment
  - Various diff calculation data structures

- **Other Internal Structures**:
  - Display label and HFID (Human Friendly ID) gathering structures
  - Internal schema processing structures
  - Benchmark and testing utilities

**Migration Path**: Existing dataclasses without `slots=True` should be migrated to use slots for performance improvements, prioritizing high-volume paths like the OGM layer.

## Consequences

### Positive

**Pydantic Benefits:**
- Automatic data validation for external inputs
- Type safety with Python type hints
- JSON serialization/deserialization
- Clear API contracts
- Field-level validation rules and descriptions
- Integration with FastAPI automatic documentation (OpenAPI/Swagger)
- Automatic schema generation for external APIs

**Slotted Dataclass Benefits:**
- **1.5x faster** instance creation compared to regular dataclasses
- **22% less memory** usage compared to regular dataclasses
- **4-5x faster** than Pydantic v2 for instance creation
- **2.6x less memory** than Pydantic v2
- No validation overhead for trusted internal data (data from database is trusted)
- Simpler syntax for internal data structures
- Better performance for high-volume internal operations (especially OGM layer)
- Python 3.13+ provides additional performance improvements

### Negative

**Pydantic Drawbacks:**
- Performance overhead for validation (acceptable for external boundaries)
- Learning curve for Pydantic features
- Some complex validations require custom validators
- Model definitions can become verbose
- Validation errors need careful error handling

**Slotted Dataclass Drawbacks:**
- No automatic validation (data must be trusted - acceptable for database data)
- Manual serialization/deserialization when needed
- No automatic API documentation generation
- Less suitable for external-facing APIs
- Requires Python 3.10+ for `slots=True` parameter (Python 3.13+ recommended for best performance)
- Cannot add attributes dynamically after class definition (by design for performance)

## Examples

### Pydantic Model (External API)

```python
from pydantic import BaseModel, Field

class ArtifactGeneratePayload(BaseModel):
    nodes: list[str] = Field(default_factory=list)
    repository_id: str = Field(..., description="Repository ID")
```

### Slotted Dataclass (Internal Query Result)

```python
from dataclasses import dataclass

@dataclass(slots=True)
class RelData:
    """Represent a relationship object in the database.
    
    Uses slots=True for performance: 1.5x faster creation, 22% less memory.
    Database data is trusted, so no validation needed.
    """
    db_id: str
    branch: str
    type: str
    status: str
```

### Message Bus (Currently Pydantic, May Change)

```python
from pydantic import Field
from infrahub.message_bus import InfrahubMessage

class RefreshGitFetch(InfrahubMessage):
    """Fetch a repository remote changes."""
    location: str = Field(..., description="The external URL of the repository")
    repository_id: str = Field(..., description="The unique ID of the repository")
```

**Note**: Internal message bus messages may migrate to dataclasses in the future, but external message contracts will remain Pydantic.

## Notes

- **External = Pydantic**: All data crossing external boundaries (REST API, GraphQL responses, events, external message contracts) uses Pydantic for validation and documentation
- **Internal = Slotted Dataclass**: All internal data structures focused on performance use `@dataclass(slots=True)`, especially in the OGM layer
- **Message Bus**: Currently Pydantic, but internal messages may migrate to slotted dataclasses for performance
- **Database Query Interface**: Uses slotted dataclasses for query results and internal data structures
- **Database Data is Trusted**: Data retrieved from the database does not require re-validation internally
- **OGM Layer Priority**: The OGM (Object Graph Mapping) layer is a high-priority area for using slotted dataclasses due to high instance creation volume
- **Python Version**: Target Python 3.13+ directly to benefit from improved dataclass performance
- **Migration**: Replace `dict[str, dict[str, str]]` patterns with properly typed slotted dataclass objects
- **Settings**: Uses Pydantic Settings for configuration management
- Type hints are required for all model fields in both approaches
- Benchmark with realistic workloads (CPU and memory profiling) when evaluating performance improvements

