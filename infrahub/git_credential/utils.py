QUERY = """
query (repository_location: !String) {
    repository(location__value: $repository_location){ 
        name {
            value
        }
        location {
            name
        }
        username {
            value
        }
        password {
            value
        }
    }
}
"""
