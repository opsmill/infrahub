# Data Model: IPAM Parent Prefix Lookup

## Existing Entities (No Schema Changes Required)

This feature operates entirely on existing data structures. No new nodes, relationships, or attributes are needed.

### BuiltinIPPrefix (existing)

Graph node representing a network prefix. Relevant attributes stored on linked `AttributeIPNetwork` value nodes:

| Property | Type | Description |
|----------|------|-------------|
| `binary_address` | `String` | Zero-padded binary representation (32 chars IPv4, 128 chars IPv6) |
| `prefixlen` | `Int` | Prefix length (e.g., 24 for /24) |
| `version` | `Int` | IP version (4 or 6) |
| `value` | `String` | CIDR notation (e.g., "10.0.0.0/8") |

**Graph path**: `(BuiltinIPPrefix)-[:HAS_ATTRIBUTE]->(Attribute {name: "prefix"})-[:HAS_VALUE]->(AttributeIPNetwork)`

### BuiltinIPNamespace (existing)

Graph node representing a logical IP address space.

**Graph path to prefix**: `(BuiltinIPNamespace)-[:IS_RELATED]-(Relationship {name: "ip_namespace__ip_prefix"})-[:IS_RELATED]-(BuiltinIPPrefix)`

### BuiltinIPAddress (existing)

Graph node representing a host address. Relevant attributes on linked `AttributeIPHost` value nodes:

| Property | Type | Description |
|----------|------|-------------|
| `binary_address` | `String` | Zero-padded binary representation |
| `prefixlen` | `Int` | Interface prefix length |
| `version` | `Int` | IP version (4 or 6) |
| `value` | `String` | Address notation (e.g., "10.1.2.45/24") |

## New Data Structures

### IPParentPrefixResult (frozen dataclass)

Query result object returned by `IPParentPrefixLookupQuery.get_data()`.

```python
@dataclass(frozen=True)
class IPParentPrefixResult:
    prefix_id: str        # UUID of the BuiltinIPPrefix node
    prefix_kind: str      # Node kind (e.g., "BuiltinIPPrefix")

    @classmethod
    def from_db(cls, result: QueryResult) -> IPParentPrefixResult:
        return cls(
            prefix_id=result.get("parent_prefix").get("uuid"),
            prefix_kind=result.get("parent_prefix").get("kind"),
        )
```

Follows the established frozen dataclass + `from_db()` pattern used by `IPPrefixFreeData`, `IPv6PrefixFreeData`, and `IPPrefixReconcileData` in the same module.

## Containment Logic

The core lookup uses the binary prefix matching algorithm already present in `IPPrefixReconcileQuery._build_possible_parent_prefixes()`:

1. Convert input IP/prefix to binary string using `convert_ip_to_binary_str()`
2. For each prefix length from `(input_prefixlen - 1)` down to `0`:
   - Take the first N bits of the binary address
   - Pad remaining bits with zeros to full length
   - Add to the list of candidate parent binary addresses
3. Match candidates against `AttributeIPNetwork.binary_address` in Neo4j
4. Filter by `version` and `prefixlen` constraints
5. Join through namespace relationship to get namespace context
6. Return results ordered by `prefixlen DESC` (most specific first)

For address inputs, use `max_prefixlen - 1` as the starting prefix length (a /32 or /128 is a host route, not a parent prefix).

## Indexes Used

- `AttributeIPNetwork(binary_address)` — existing index, used for the `IN $possible_prefix_list` match
- No new indexes required
