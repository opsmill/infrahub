QUERY_ALL_REPOSITORIES = """
query {
    CoreRepository {
        count
        edges {
            node {
                id
                name {
                    value
                }
                location {
                    value
                }
                commit {
                    value
                }
            }
        }
    }
}
"""


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
QUERY_BRANCH_DIFF = """
            query($branch_name: String!, $branch_only: Boolean!, $diff_from: String!, $diff_to: String! ) {
                diff(branch: $branch_name, branch_only: $branch_only, time_from: $diff_from, time_to: $diff_to ) {
                    nodes {
                        branch
                        kind
                        id
                        changed_at
                        action
                        attributes {
                            name
                            id
                            changed_at
                            action
                            properties {
                                action
                                type
                                changed_at
                                branch
                                value {
                                    previous
                                    new
                                }
                            }
                        }
                    }
                    relationships {
                        branch
                        id
                        name
                        properties {
                            branch
                            type
                            changed_at
                            action
                            value {
                                previous
                                new
                            }
                        }
                        nodes {
                            id
                            kind
                        }
                        changed_at
                        action
                    }
                    files {
                        action
                        repository
                        branch
                        location
                    }
                }
            }
            """

MUTATION_COMMIT_UPDATE = """
mutation ($repository_id: String!, $commit: String!) {
    CoreRepositoryUpdate(data: { id: $repository_id, commit: { value: $commit } }) {
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
