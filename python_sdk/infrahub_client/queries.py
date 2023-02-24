QUERY_ALL_REPOSITORIES = """
query {
    repository {
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
"""

QUERY_ALL_GRAPHQL_QUERIES = """
query {
    graphql_query {
        id
        name {
            value
        }
        description {
            value
        }
        query {
            value
        }
    }
}
"""

QUERY_ALL_RFILES = """
query {
    rfile {
        id
        name {
            value
        }
        description {
            value
        }
        template_path {
            value
        }
        template_repository {
            id
            name {
                value
            }
        }
        query {
            id
            name {
                value
            }
        }
    }
}
"""

QUERY_ALL_CHECKS = """
query {
    check {
        id
        name {
            value
        }
        description {
            value
        }
        file_path {
            value
        }
        class_name {
            value
        }
        rebase {
            value
        }
        timeout {
            value
        }
        query {
            id
            name {
                value
            }
        }
        repository {
            id
            name {
                value
            }
        }
    }
}
"""

QUERY_ALL_TRANSFORM_PYTHON = """
query {
    transform_python {
        id
        name {
            value
        }
        description {
            value
        }
        file_path {
            value
        }
        class_name {
            value
        }
        rebase {
            value
        }
        timeout {
            value
        }
        url {
            value
        }
        query {
            id
            name {
                value
            }
        }
        repository {
            id
            name {
                value
            }
        }
    }
}
"""

QUERY_ALL_BRANCHES = """
query {
    branch {
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

MUTATION_BRANCH_CREATE = """
mutation ($branch_name: String!, $description: String!, $background_execution: Boolean!, $data_only: Boolean!) {
    branch_create(background_execution: $background_execution, data: { name: $branch_name, description: $description, is_data_only: $data_only }) {
        ok
        object {
            id
            name
            description
            origin_branch
            branched_from
            is_default
            is_data_only
        }
    }
}
"""

MUTATION_BRANCH_REBASE = """
mutation ($branch_name: String!) {
    branch_rebase(data: { name: $branch_name }){
        ok
        object {
            name
            branched_from
        }
    }
}
"""

MUTATION_BRANCH_VALIDATE = """
mutation ($branch_name: String!) {
    branch_validate(data: { name: $branch_name }) {
        ok
        messages
        object {
            id
            name
        }
    }
}
"""

MUTATION_BRANCH_MERGE = """
mutation ($branch_name: String!) {
    branch_merge(data: { name: $branch_name }) {
        ok
        object {
            id
            name
        }
    }
}
"""

MUTATION_COMMIT_UPDATE = """
mutation ($repository_id: String!, $commit: String!) {
    repository_update(data: { id: $repository_id, commit: { value: $commit } }) {
        ok
        object {
            commit {
                value
            }
        }
    }
}
"""


MUTATION_GRAPHQL_QUERY_CREATE = """
mutation($name: String!, $description: String!, $query: String!) {
  graphql_query_create(data: {
    name: { value: $name },
    description: { value: $description },
    query: { value: $query }}){
        ok
        object {
            id
            name {
                value
            }
        }
    }
}
"""

MUTATION_GRAPHQL_QUERY_UPDATE = """
mutation($id: String!, $name: String!, $description: String!, $query: String!) {
  graphql_query_update(data: {
    id: $id
    name: { value: $name },
    description: { value: $description },
    query: { value: $query }}){
        ok
        object {
            id
            name {
                value
            }
        }
    }
}
"""

MUTATION_RFILE_CREATE = """
mutation($name: String!, $description: String!, $template_path: String!, $template_repository: String!, $query: String!) {
  rfile_create(data: {
    name: { value: $name },
    description: { value: $description },
    query: { id: $query }
    template_path: { value: $template_path }
    template_repository: { id: $template_repository }}){
        ok
        object {
            id
            name {
                value
            }
        }
    }
}
"""

MUTATION_RFILE_UPDATE = """
mutation($id: String!, $name: String!, $description: String!, $template_path: String!) {
  rfile_update(data: {
    id: $id
    name: { value: $name },
    description: { value: $description },
    template_path: { value: $template_path }}){
        ok
        object {
            id
            name {
                value
            }
        }
    }
}
"""

MUTATION_CHECK_CREATE = """
mutation($name: String!, $description: String!, $file_path: String!, $class_name: String!, $repository: String!, $query: String!, $timeout: Int!, $rebase: Boolean!) {
  check_create(data: {
    name: { value: $name }
    description: { value: $description }
    query: { id: $query }
    file_path: { value: $file_path }
    class_name: { value: $class_name }
    repository: { id: $repository }
    timeout: { value: $timeout }
    rebase: { value: $rebase }
  }){
        ok
        object {
            id
            name {
                value
            }
        }
    }
}
"""

MUTATION_CHECK_UPDATE = """
mutation($id: String!, $name: String!, $description: String!, $file_path: String!, $class_name: String!, $query: String!, $timeout: Int!, $rebase: Boolean!) {
  check_update(data: {
    id: $id
    name: { value: $name },
    description: { value: $description },
    file_path: { value: $file_path },
    class_name: { value: $class_name },
    query: { id: $query },
    timeout: { value: $timeout },
    rebase: { value: $rebase },
  }){
        ok
        object {
            id
            name {
                value
            }
        }
    }
}
"""


MUTATION_TRANSFORM_PYTHON_CREATE = """
mutation($name: String!, $description: String!, $file_path: String!, $class_name: String!, $repository: String!, $query: String!, $url: String!, $timeout: Int!, $rebase: Boolean!) {
  transform_python_create(data: {
    name: { value: $name }
    description: { value: $description }
    query: { id: $query }
    file_path: { value: $file_path }
    url: { value: $url }
    class_name: { value: $class_name }
    repository: { id: $repository }
    timeout: { value: $timeout }
    rebase: { value: $rebase }
  }){
        ok
        object {
            id
            name {
                value
            }
        }
    }
}
"""

MUTATION_TRANSFORM_PYTHON_UPDATE = """
mutation($id: String!, $name: String!, $description: String!, $file_path: String!, $class_name: String!, $query: String!, $url: String!, $timeout: Int!, $rebase: Boolean!) {
  transform_python_update(data: {
    id: $id
    name: { value: $name },
    description: { value: $description },
    file_path: { value: $file_path },
    class_name: { value: $class_name },
    url: { value: $url },
    query: { id: $query },
    timeout: { value: $timeout },
    rebase: { value: $rebase },
  }){
        ok
        object {
            id
            name {
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
