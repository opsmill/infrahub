QUERY_ALL_BRANCHES = """
query {
    Branch {
        id
        name
        description
        origin_branch
        branched_from
        is_default
        is_data_only
    }
}
"""

QUERY_BRANCH = """
query GetBranch($branch_name: String!) {
    Branch(name: $branch_name) {
        id
        name
        description
        origin_branch
        branched_from
        is_default
        is_data_only
    }
}
"""


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


QUERY_SCHEMA = """
    query {
        node_schema {
            name {
                value
            }
            kind {
                value
            }
            inherit_from {
                value
            }
            description {
                value
            }
            default_filter {
                value
            }
            attributes {
                name {
                    value
                }
                kind {
                    value
                }
                optional {
                    value
                }
                unique {
                    value
                }
                default_value {
                    value
                }
            }
            relationships {
                name {
                    value
                }
                peer {
                    value
                }
                identifier {
                    value
                }
                cardinality {
                    value
                }
                optional {
                    value
                }
            }
        }
    }
    """
