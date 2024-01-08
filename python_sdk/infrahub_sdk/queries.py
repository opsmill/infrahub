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


MUTATION_COMMIT_UPDATE = """
mutation ($repository_id: String!, $commit: String!) {
    CoreRepositoryUpdate(data: { id: $repository_id, commit: { is_protected: true, source: $repository_id, value: $commit } }) {
        ok
        object {
            commit {
                value
            }
        }
    }
}
"""


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
