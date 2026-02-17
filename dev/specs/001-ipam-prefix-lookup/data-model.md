# Data Model: IPAM Parent Prefix Lookup

## Existing Entities (No Changes)

### AttributeIPNetwork (Neo4j Node)
Label: `AttributeIPNetwork`

| Property        | Type   | Description                          | Indexed |
|-----------------|--------|--------------------------------------|---------|
| value           | string | Human-readable prefix (e.g., "10.1.2.0/24") | No |
| binary_address  | string | Binary representation of network address | RANGE |
| version         | int    | IP version (4 or 6)                  | No      |
| prefixlen       | int    | Prefix length (e.g., 24)             | No      |
| is_default      | bool   | Whether this is the default value    | No      |

### AttributeIPHost (Neo4j Node)
Label: `AttributeIPHost`

| Property        | Type   | Description                          | Indexed |
|-----------------|--------|--------------------------------------|---------|
| value           | string | Human-readable address (e.g., "10.1.2.45/24") | No |
| binary_address  | string | Binary representation of IP address  | RANGE |
| version         | int    | IP version (4 or 6)                  | No      |
| prefixlen       | int    | Prefix length of the network portion | No      |
| is_default      | bool   | Whether this is the default value    | No      |

### Graph Relationships (Existing)

```
(BuiltinIPNamespace)-[:IS_RELATED]-(Relationship {name: "ip_namespace__ip_prefix"})-[:IS_RELATED]-(BuiltinIPPrefix)
(BuiltinIPPrefix)-[:HAS_ATTRIBUTE]->(Attribute {name: "prefix"})-[:HAS_VALUE]->(AttributeIPNetwork)
```

## New Data Structures

### IPParentPrefixLookupResult (Python dataclass)

```python
@dataclass(frozen=True)
class IPParentPrefixResult:
    """A single parent prefix result from the lookup query."""
    prefix_id: str          # UUID of the BuiltinIPPrefix node
    prefix_value: str       # Human-readable prefix (e.g., "10.1.2.0/24")
    prefix_length: int      # Prefix length for ordering
    namespace_id: str       # UUID of the BuiltinIPNamespace node
    namespace_name: str     # Display name of the namespace
```

### GraphQL Response Extension

The existing `NodeEdges` response type is extended with a boolean flag:

```graphql
type NodeEdges {
  count: Int!
  edges: [NodeEdge!]!
  is_prefix_lookup: Boolean  # NEW: true when results are from IP prefix containment lookup
}
```

## Query Data Flow

```
Input: "10.1.2.45"
  ↓ ipaddress.ip_address("10.1.2.45")
  ↓ convert_ip_to_binary_str → "00001010000000010000001000101101"
  ↓ Generate possible_prefix_list for lengths 32→0
  ↓
Cypher: MATCH (ns:BuiltinIPNamespace)→(Relationship)→(pfx:BuiltinIPPrefix)→(Attribute)→(av:AttributeIPNetwork)
        WHERE av.binary_address IN $possible_prefix_list
              AND av.prefixlen <= corresponding_max_length
              AND av.version = $ip_version
  ↓
Result: [{prefix_id, prefix_value, prefix_length, namespace_id, namespace_name}, ...]
  ↓ Order by prefix_length DESC (most specific first)
  ↓
GraphQL: {count, edges: [{node: {id, kind}}], is_prefix_lookup: true}
```
