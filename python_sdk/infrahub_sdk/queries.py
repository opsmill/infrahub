def get_commit_update_mutation(is_read_only: bool = False) -> str:
    mutation_commit_update_base = """
    mutation ($repository_id: String!, $commit: String!) {{
        {repo_class}Update(data: {{ id: $repository_id, commit: {{ is_protected: true, source: $repository_id, value: $commit }} }}) {{
            ok
            object {{
                commit {{
                    value
                }}
            }}
        }}
    }}
    """
    if is_read_only:
        return mutation_commit_update_base.format(repo_class="CoreReadOnlyRepository")
    return mutation_commit_update_base.format(repo_class="CoreRepository")


QUERY_RELATIONSHIPS = """
    query GetRelationships($relationship_identifiers: [String!]!) {
        Relationship(ids: $relationship_identifiers) {
            count
            edges {
                node {
                    identifier
                    peers {
                        id
                        kind
                    }
                }
            }
        }
    }
"""

SCHEMA_HASH_SYNC_STATUS = """
query {
  InfrahubStatus {
    summary {
      schema_hash_synced
    }
  }
}
"""
